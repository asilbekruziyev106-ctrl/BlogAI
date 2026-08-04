import os
import io
import json
import base64
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
import fitz  # PyMuPDF library PDF fayllar uchun
import telebot

# ---------------------------------------------------------------------------
# GEMINI API (OCR, Matn, Savol va Hashtag uchun)
# ---------------------------------------------------------------------------
def process_image_with_gemini(image_bytes):
    """
    Rasm yoki PDF sahifasidan matn o'qiydi, sarlavhani ajratadi,
    o'zidan gap qo'shmasdan lotincha matn va postga oid savol yaratadi.
    """
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={GEMINI_API_KEY}"
    
    base64_img = base64.b64encode(image_bytes).decode('utf-8')

    prompt = """
    Sen @RuziyevAsilbek Telegram kanali uchun mas'ul bo'lgan aniq va talabchan AI muharrirsan.
    Ushbu sahifani/rasmni tahlil qil va QUYIDAGI MUTLAQ QOIDALARGA AMAL QILGAN HOLDA JAVOB BERING:

    1. SARLAVHA AJRATISH:
       - Sahifa ichidagi MATNLAR O'RTASIDA joylashgan QALIN (BOLD) yozuvlarni, markazlashgan matnlarni yoki HAMMA HARFLARI KATTA bilan yozilgan asosiy sarlavhani ajratib ol.

    2. MATN ANIQ LIGI (O'ZINGDAN GAP QO'SHMA):
       - Rasmdagi/PDF dagi kitob matnidan BO'SHQA JOYGA O'TIB KETMA.
       - O'zingdan hech qanday ortiqcha gap, fikr yoki so'z qo'shma.
       - Matnni to'liq va grammatik imlo xatolarsiz O'ZBEK LOTIN alifbosida aynan ko'chirib ber.
       - Ortiqcha kirish so'zlari ("Mana sizga post", "Albatta", "Tushundim") ISHLATMA.

    3. POSTGA OID SAVOL:
       - Post o'quvchilarida qiziqish uyg'otishi uchun post mazmuniga bevosita daxldor bo'lgan 1 TA QIZIQARLI SAVOL tuz.

    4. DIZAYN QARORI:
       - Ushbu sarlavha va matn uchun AI tomonidan visual dizayn banner rasmi yaratilishi lozimmi yoki yozuvning o'zi yetarlimi? (needsBanner: true/false).
       - Banner uchun inglizcha prompt tayyorla (bannerPrompt).

    5. HASHTAGLAR:
       - Post mazmuniga mos 3 ta chiroyli hashtag tuz (masalan: #oila #kitob #tarbiya).

    Javobni FAQAT QUYIDAGI SOF JSON FORMATIDA QAYTARING:
    {
      "sarlavha": "SARLAVHA SHU YERDA",
      "matn": "Kitobdan aniq ko'chirilgan xatosiz lotincha matn...",
      "savol": "Postga oid qiziqarli savol?",
      "needsBanner": true,
      "bannerPrompt": "A modern graphic design illustration for book post titled...",
      "hashtags": "#oila #kitob #tarbiya"
    }
    """

    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {
                    "inlineData": {
                        "mimeType": "image/jpeg",
                        "data": base64_img
                    }
                }
            ]
        }],
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }

    response = requests.post(url, json=payload)
    if response.status_code == 200:
        result = response.json()
        raw_text = result['candidates'][0]['content']['parts'][0]['text']
        return json.loads(raw_text)
    else:
        raise Exception(f"Gemini API xatoligi: {response.text}")

# ---------------------------------------------------------------------------
# IMAGEN API (Banner Rasm Generatsiyasi)
# ---------------------------------------------------------------------------
def generate_banner_image(prompt_text):
    """Sarlavhaga mos grafik banner yaratadi"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-002:predict?key={GEMINI_API_KEY}"
    payload = {
        "instances": [{"prompt": prompt_text}],
        "parameters": {"sampleCount": 1}
    }
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            bytes_b64 = response.json()['predictions'][0]['bytesBase64Encoded']
            return base64.b64decode(bytes_b64)
    except Exception:
        pass
    return None

# ---------------------------------------------------------------------------
# TELEGRAM BOT HANDLERLARI
# ---------------------------------------------------------------------------
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(
        message,
        "Assalomu alaykum! Men @RuziyevAsilbek kanalining avtomatik blog yordamchisiman.\n\n"
        "📸 Kitob sahifasi rasmini yuboring\n"
        "📄 Yoki PDF kitob faylini yuboring\n\n"
        "Men matnni aniq lotin tiliga o'giraman, sarlavhani topaman va tayyor post shakllantirib beraman!"
    )

@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    status_msg = bot.reply_to(message, "⏳ Rasm tahlil qilinmoqda, kuting...")
    try:
        # Rasmni yuklab olish
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)

        # Gemini API ga yuborish
        data = process_image_with_gemini(downloaded_file)

        # Post tekstini shakllantirish
        caption_text = (
            f"<b>{data['sarlavha'].upper()}</b>\n\n"
            f"{data['matn']}\n\n"
            f"❓ {data['savol']}\n\n"
            f"{CHANNEL_LINK}\n\n"
            f"{data['hashtags']}"
        )

        bot.delete_message(message.chat.id, status_msg.message_id)

        # Banner kerak bo'lsa Imagen orqali rasm yaratish
        if data.get('needsBanner') and data.get('bannerPrompt'):
            banner_status = bot.send_message(message.chat.id, "🎨 Sarlavhaga mos dizayn rasm yaratilmoqda...")
            banner_bytes = generate_banner_image(data['bannerPrompt'])
            bot.delete_message(message.chat.id, banner_status.message_id)

            if banner_bytes:
                bot.send_photo(message.chat.id, banner_bytes, caption=caption_text, parse_mode="HTML")
                return

        # Banner kerak bo'lmasa yozuvning o'zini yuborish
        bot.send_message(message.chat.id, caption_text, parse_mode="HTML")

    except Exception as e:
        bot.reply_to(message, f"❌ Xatolik yuz berdi: {str(e)}")

@bot.message_handler(content_types=['document'])
def handle_document(message):
    if not message.document.mime_type == 'application/pdf':
        bot.reply_to(message, "Iltimos, faqat PDF formatidagi kitob faylini yuboring.")
        return

    status_msg = bot.reply_to(message, "⏳ PDF sahifasi qayta ishlanmoqda...")

    try:
        file_info = bot.get_file(message.document.file_id)
        pdf_bytes = bot.download_file(file_info.file_path)

        # PDF dan 1-sahifani rasmga aylantirish
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        page = doc.load_page(0)
        pix = page.get_pixmap(dpi=150)
        img_bytes = pix.tobytes("jpeg")

        data = process_image_with_gemini(img_bytes)

        caption_text = (
            f"<b>{data['sarlavha'].upper()}</b>\n\n"
            f"{data['matn']}\n\n"
            f"❓ {data['savol']}\n\n"
            f"{CHANNEL_LINK}\n\n"
            f"{data['hashtags']}"
        )

        bot.delete_message(message.chat.id, status_msg.message_id)

        if data.get('needsBanner') and data.get('bannerPrompt'):
            banner_bytes = generate_banner_image(data['bannerPrompt'])
            if banner_bytes:
                bot.send_photo(message.chat.id, banner_bytes, caption=caption_text, parse_mode="HTML")
                return

        bot.send_message(message.chat.id, caption_text, parse_mode="HTML")

    except Exception as e:
        bot.reply_to(message, f"❌ PDF o'qishda xatolik: {str(e)}")

if __name__ == "__main__":
    print("Bot va Health Check server 7/24 rejimida ishga tushdi...")
    bot.infinity_polling()
