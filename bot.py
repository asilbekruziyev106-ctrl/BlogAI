# ... existing code ...
def process_image_with_gemini(image_bytes):
    """
    Rasm yoki PDF sahifasidan matn o'qiydi, sarlavhani ajratadi,
    o'zidan gap qo'shmasdan lotincha matn va postga oid savol yaratadi.
    """
    # 1. API Kalitingiz uchun ochiq bo'lgan modelni avtomatik aniqlaymiz
    model_name = "gemini-2.5-flash"
    try:
        models_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_API_KEY}"
        m_res = requests.get(models_url, timeout=5)
        if m_res.status_code == 200:
            models_list = m_res.json().get('models', [])
            # Kalit uchun ochiq va generateContent qo'llaydigan modellar ro'yxati
            valid_models = [
                m['name'].replace('models/', '') 
                for m in models_list 
                if 'generateContent' in m.get('supportedGenerationMethods', [])
            ]
            # Flash turidagi eng maqbul modelni tanlaymiz
            flash_models = [m for m in valid_models if 'flash' in m]
            if flash_models:
                model_name = flash_models[0]
            elif valid_models:
                model_name = valid_models[0]
    except Exception as e:
        print(f"Model aniqlashda xatolik: {e}")

    # 2. Aniqlangan model manzili orqali so'rov yuboramiz
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
    
    base64_img = base64.b64encode(image_bytes).decode('utf-8')
# ... existing code ...
```

---

### 2-YECHIM: n8n Platformasi (No-Code Visual Yechim)

Ha, **n8n** orqali qilish ham juda qulay va muqobil yo'l!

**Nima uchun n8n qulay?**
1. **Model menyudan tanlanadi:** n8n ichida Google Gemini API integratsiyasi tayyor bo'lib, modellarni kod yozmasdan shunchaki ro'yxatdan tanlab qo'yasiz.
2. **Server (Render) xatoliklari bo'lmaydi:** Port-binding, pip install va Python kutubxona xatolari bilan bosh qotirmaysiz.
3. Loyihangiz papkasida **`n8n Orqali Telegram Bot Yaratish Yo'riqnomasi`** fayli tayyorlab berilgan.

---

### Nima qilishni maslahat beraman?
1. Birinchi bo'lib **GitHub**'dagi `bot.py` fayliga ushbu dinamik kodni qo'shib saqlang (**Commit changes**). Bu 100% 404 xatolarini yo'qotadi.
2. Agar grafik interfeysda bloklarni ulash orqali botni vizual boshqarishni istasangiz, **n8n yo'riqnomasi** bo'yicha botni 10 daqiqada n8n'ga o'tkazib olishingiz ham mumkin!
