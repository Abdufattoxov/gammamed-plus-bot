# 🏥 "Gammamed Plus" — Professional Tibbiyot Telegram Boti (Dr. Zarifa)

Ginekolog-psixosomatika mutaxassisi **Dr. Zarifa** va **«Gammamed Plus»** klinikasi uchun bemorlar ma'lumotlarini to'plovchi, qabulga yozuvchi hamda klinika xizmatlarini taqdim etuvchi professional va tezkor Telegram bot.

---

## 🌟 Asosiy Imkoniyatlar va Yangilanishlar

1. **🏛 Asosiy Menyu:**
   - 📅 **Qabulga yozilish:** Tezkor 3 bosqichli konversiyaviy oqim.
   - 🩺 **Xizmatlarimiz:** Klinikaning barcha ixtisoslashuv yo‘nalishlari (narxlar yozilmaydi, qo‘ng‘iroq orqali aniqlashtiriladi).
   - 👩‍⚕️ **Shifokor haqida:** Dr. Zarifaning 30 yillik chuqur tajribasi, asosiy yo‘nalishlari va fotosurati.
   - 📍 **Manzil va ish vaqti:** Samarqand viloyati, Bulung‘ur tumani, «Yulduz» kinoteatri yonidagi «Gammamed» (Gammamed Plus) klinikasi.
   - ❓ **Anonim savol berish:** Bemorlar o'zlarini qiynayotgan nozik savollarni shaxsini oshkor qilmagan holda shifokorga yo'llashlari mumkin.

2. **⚡️ Tezkor Target Voronka (Deep-link & 3 bosqichli FSM):**
   - **Deep-link:** `/start bulungur_ads` orqali kirgan foydalanuvchiga asosiy menyusiz darhol 1-bosqich ko'rsatiladi.
   - **Asosiy taklif (Offer):** *«Bitta qabulning o‘zida siz va turmush o‘rtog‘ingiz birgalikda suhbatdan o‘tasiz, barcha eski analizlaringiz ko‘rib chiqiladi va Dr. Zarifa uyda bajarish uchun shaxsiy yo‘l xaritasi hamda mashqlarni qo‘lingizga aniq yozib beradi.»*
   - **1-bosqich: Muammoni tanlash:** Inline tugmalar (Bepushtlik, Hayz og‘riqlari, Ikkala muammo, Boshqa muammo).
   - **2-bosqich: Ism-familiya:** Matn ko'rinishida kiritish (`⬅️ Orqaga` va `❌ Bekor qilish` tugmalari bilan).
   - **3-bosqich: Telefon raqami:** `📱 Telefon raqamni yuborish` tugmasi yoki `+998...` formatida matn.
   - **Darhol yakunlash:** Telefon raqami kiritilishi bilan ariza bazaga saqlanadi va adminga yuboriladi.

3. **🔔 Admin Bildirishnomalari va Excel Eksport:**
   - Har bir yangi ariza va anonim savol to‘g‘ridan-to‘g‘ri `ADMIN_IDS` (shaxsiy Telegram) ga yuboriladi (`ADMIN_GROUP_ID` bo‘sh bo‘lsa ham xatosiz ishlaydi).
   - Ariza holatini o‘zgartirishda (`✅ Qabul qilindi`, `📞 Qo‘ng‘iroq qilindi`) HTML format buzilmaydi.
   - `/admin` panelidagi `📥 Baza (Excel)` tugmasi bosilganda barcha arizalar (ID, Sana/Vaqt, Bemor ismi, Telefon raqami, Tanlangan muammo, Holati) chiroyli `.xlsx` formatida yuklab beriladi.

4. **⚡️ Tezkorlik va Tozalik (TTS o‘chirilgan):**
   - Hech qanday ovozli xabarlar kutubxonasisiz (`edge-tts` olib tashlangan), bot juda tez va kechikishsiz ishlaydi.

---

## 📁 Loyiha Strukturasi

```text
├── bot.py             # Botni ishga tushirish, dispatcher, logging
├── handlers.py        # Buyruqlar, menyu, 3 bosqichli FSM oqimi va admin handlerlari
├── keyboards.py       # Reply va Inline tugmalar
├── states.py          # aiogram FSM holatlari (StatesGroup)
├── database.py        # SQLite (aiosqlite) va Excel (.xlsx) eksport moduli
├── config.py          # .env sozlamalari, klinika ma'lumotlari va matnlar
├── requirements.txt   # Kerakli Python kutubxonalari
├── doctor_photo.jpg   # Shifokor profili va avatari fotosurati
├── .env.example       # Konfiguratsiya namunasi
└── README.md          # Foydalanish qo'llanmasi
```

---

## 🚀 Ishga Tushirish

```bash
# 1. Kutubxonalarni o'rnatish
pip install -r requirements.txt

# 2. .env faylini sozlash
# BOT_TOKEN va ADMIN_IDS kiritiladi

# 3. Botni ishga tushirish
python bot.py
```
