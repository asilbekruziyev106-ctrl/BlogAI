import os
import sys
import json
import base64
import threading
import http.server
import socketserver
import requests
import telebot
import fitz  # PyMuPDF

# Muhit o'zgaruvchilarini olish
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not TELEGRAM_BOT_TOKEN or not GEMINI_API_KEY:
    print("XATOLIK: TELEGRAM_BOT_TOKEN yoki GEMINI_API_KEY muhit o'zgaruvchilari topilmadi!")
    sys.exit(1)

bot = telebot.TeleBot(TELEGRAM_BOT_TOKEN)

# ---------------------------------------------------------
# Render.com Port Health Check Server (Port yopilmasligi uchun)
# ---------------------------------------------------------
class HealthCheckHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write("OK - Bot muvaffaqiyatli ishlayapti".encode("utf-8"))

    def log_message(self, format, *args):
        return  # Server loglarini tozalash

def start_health_server():
    port = int(os.environ.get("PORT", 8080))
    try:
        with socketserver.TCPServer(("", port), HealthCheckHandler) as httpd:
            print(f"Health check server {port}-portda ishga tushdi...")
            httpd.serve_forever()
    except Exception as e:
        print(f"Port serverida xatolik: {e}")

# ---------------------------------------------------------
# Google Gemini API Dinamik Model Tanlash
# ---------------------------------------------------------
def get_working_gemini_model():
    """
    Sizning API Kalitingiz uchun ochiq bo'lgan eng maqbul Gemini modelini
    otvomatik aniqlab beradi (404 xatolarining oldini oladi).
    """
    fallback_model = "gemini-1.5-flash"
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
        res = requests.get(url, timeout=8)
        if res.status_code == 200:
            models_list = res.json().get('models', [])
            
            # Content generate qila oladigan modellar ro'yxati
            valid_models = [
                m['name'].replace('models/', '') 
                for m in models_list 
                if 'generateContent' in m.get('supportedGenerationMethods', [])
            ]
            
            # Flash turidagi eng yangi modelni birinchi tanlaymiz
            flash_models = [m for m in valid_models if 'flash' in m]
            if flash_models:
                return flash_models[0]
            elif valid_models:
                return valid_models[0]
    except Exception as e:
        print(f"Model aniqlashda xatolik: {e}")
        
    return fallback_model

def process_image_with_gemini(image_bytes):
    """
    Rasm yoki PDF sahifasidan matn o'qiydi, sarlavhani ajratadi,
    o'zidan gap qo'shmasdan lotincha matn va postga oid savol yaratadi.
    """
    active_model = get_working_gemini_model()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{active_model}:generateContent?key={GEMINI_API_KEY}"
    
    base64_img = base64.b64encode(image_bytes).decode('utf-8')

    prompt = """
Sen Telegram kanali uchun matn tayyorlovchi professional AI muharrirsan.
Rasmdagi matnni o'rganib chiq va quyidagi qat'iy talablar bo'yicha javob tayyorla:

1. **SARLAVHA:** Rasmdagi asosiy qalin (bold) yozilgan yoki katta harfli sarlavhani top va uni BIRINCHI QATORGA KATTA HARFLARDA yoz.
2. **MATN KO'CHIRISH:** Rasmdagi kitob/sahifa matnini 100% aniqlikda, o'zingdan birorta so'z yoki gap qo'shmasdan va xatosiz O'ZBEK LOTIN alifbosida ko'chirib ber. Ortiqcha kirish-chiqish gaplari yozma.
3. **QIZIQARLI SAVOL:** Post oxiriga matn mazmuniga oid 1 TA qiziqarli savol qo'sh.
4. **KANAL LINKI:** Savoldan so'ng 1 ta bo'sh qator tashlab `📖 @RuziyevAsilbek` linkini qo'sh.
5. **HASHTAGLAR:** Linkdan so'ng 1 ta bo'sh qator tashlab post mazmuniga mos 3 ta hashtag (#oila #kitob kabi) qo'sh.

Format aynan quyidagicha bo'lsin:
SARLAVHA

Kitobdan ko'chirilgan matn...

❓ [Mavzuga oid qiziqarli savol?]

📖 @RuziyevAsilbek

#hashtag1 #hashtag2 #hashtag3
"""

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {
                        "inlineData": {
                            "mimeType": "image/jpeg",
                            "data": base64_img
                        }
                    }
                ]
            }
        ]
    }

    try:
        response = requests.post(
            url, 
            json=payload, 
            headers={"Content-Type": "application/json"}, 
            timeout=35
        )
        
        if response.status_code == 200:
            result = response.json()
            return result['candidates'][0]['content']['parts'][0]['text']
        else:
            return f"❌ Gemini API xatoligi ({response.status_code}): {response.text}"
    except Exception as e:
        return f"❌ AI ulanishida xatolik yuz berdi: {e}"

# ---------------------------------------------------------
# Telegram Bot Buyruqlari va Handlerlar
# ---------------------------------------------------------
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(
        message,
        "Assalomu alaykum! Men kitob sahifasi rasmi yoki PDF fayllarini o'qib, "
        "Telegram kanal uchun tayyor post qilib beruvchi AI botman.\n\n"
        "Menga kitob sahifasi rasmini yoki PDF fayl yuboring!"
    )

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    msg = bot.reply_to(message, "⏳ Rasm tahlil qilinmoqda, kuting...")
    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        result_text = process_image_with_gemini(downloaded_file)
        bot.edit_message_text(result_text, message.chat.id, msg.message_id)
    except Exception as e:
        bot.edit_message_text(f"❌ Xatolik yuz berdi: {e}", message.chat.id, msg.message_id)

@bot.message_handler(content_types=['document'])
def handle_document(message):
    if not message.document.mime_type or 'pdf' not in message.document.mime_type.lower():
        bot.reply_to(message, "Iltimos, faqat PDF formatidagi fayl yoki rasm yuboring.")
        return

    msg = bot.reply_to(message, "⏳ PDF yuklanmoqda va birinchi sahifasi tahlil qilinmoqda...")
    try:
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        # PyMuPDF orqali PDF birinchi sahifasini rasmga aylantirish
        doc = fitz.open(stream=downloaded_file, filetype="pdf")
        if len(doc) == 0:
            bot.edit_message_text("❌ PDF fayli bo'sh ko'rinadi.", message.chat.id, msg.message_id)
            return

        page = doc[0]
        pix = page.get_pixmap(dpi=150)
        img_bytes = pix.tobytes("jpeg")

        result_text = process_image_with_gemini(img_bytes)
        bot.edit_message_text(result_text, message.chat.id, msg.message_id)
    except Exception as e:
        bot.edit_message_text(f"❌ PDF ishlanishida xatolik: {e}", message.chat.id, msg.message_id)

# ---------------------------------------------------------
# Botni Ishga Tushirish
# ---------------------------------------------------------
if __name__ == '__main__':
    # Render.com portini ochib turish uchun fon rejimida veb-server yaratamiz
    threading.Thread(target=start_health_server, daemon=True).start()
    
    print("Telegram Bot ishga tushdi...")
    bot.infinity_polling(timeout=20, long_polling_timeout=5)
