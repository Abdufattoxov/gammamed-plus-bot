import os
from dotenv import load_dotenv

# .env faylini yuklash
load_dotenv()

# Bot sozlamalari
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

# Asosiy adminlar ro'yxati
DEFAULT_ADMIN_IDS: list[int] = [5137101785, 8905303990]

# Adminlar ID ro'yxati (.env faylidan o'qish va asosiy adminlarni birlashtirish)
admin_ids_raw = os.getenv("ADMIN_IDS", "")
ADMIN_IDS: list[int] = list(set(
    DEFAULT_ADMIN_IDS + [
        int(x.strip()) for x in admin_ids_raw.split(",") if x.strip().isdigit()
    ]
))

# Admin guruhi yoki kanali ID si (ixtiyoriy: arizalar guruhga ham tushishi uchun)
admin_group_raw = os.getenv("ADMIN_GROUP_ID", "")
ADMIN_GROUP_ID: int | None = int(admin_group_raw) if admin_group_raw and (admin_group_raw.lstrip("-").isdigit()) else None

# Ma'lumotlar bazasi sozlamalari
DATABASE_NAME: str = os.getenv("DATABASE_NAME", "gammamed.db")
DATABASE_URL: str = os.getenv("DATABASE_URL", "")

# Google Sheets integratsiyasi (Lidlar doimiy Google Sheets jadvaliga tushishi uchun)
GOOGLE_SHEET_WEBHOOK_URL: str = os.getenv("GOOGLE_SHEET_WEBHOOK_URL", "")
GOOGLE_SHEET_URL: str = os.getenv("GOOGLE_SHEET_URL", "")

# Meta Ads (Instagram / Facebook Target) API sozlamalari
META_ACCESS_TOKEN: str = os.getenv("META_ACCESS_TOKEN", "")
META_AD_ACCOUNT_ID: str = os.getenv("META_AD_ACCOUNT_ID", "1514294217269797")
USD_TO_UZS: int = int(os.getenv("USD_TO_UZS", "12850"))

# Klinika va shifokor ma'lumotlari
CLINIC_NAME: str = "Gammamed Plus"
CLINIC_NAME_COMMON: str = "«Gammamed» klinikasi"
DOCTOR_NAME: str = "Dr. Zarifa"
DOCTOR_TITLE: str = "30 yillik tajribaga ega akusher-ginekolog, ginekolog-psixosomatik"
DOCTOR_SPECIALTY: str = (
    "Bepushtlik (farzand ko‘ra olmaslik, analizlar toza bo‘lsa ham homila bo‘lmasligi), "
    "hayz oldi va hayz davridagi kuchli og‘riqlar, gormonal va psixosomatik muammolar."
)
CLINIC_ADDRESS: str = os.getenv(
    "CLINIC_ADDRESS",
    "Samarqand viloyati, Bulung‘ur tumani, «Yulduz» kinoteatri yonidagi «Gammamed» (Gammamed Plus) klinikasi"
)
CLINIC_WORKING_HOURS: str = "Dushanba — Shanba: 09:00 dan 17:00 gacha\nYakshanba: Dam olish kuni"

# Asosiy taklif (Offer) va qabul narxi
CONSULTATION_PRICE: str = os.getenv("CONSULTATION_PRICE", "90 000 so‘m")
TOTAL_CONSULTATION_PRICE: int = int(os.getenv("TOTAL_CONSULTATION_PRICE", "90000"))
PREPAYMENT_BASE: int = int(os.getenv("PREPAYMENT_BASE", "30000"))

# Plastik karta to'lov ma'lumotlari
PAYMENT_CARD_NUMBER: str = os.getenv("PAYMENT_CARD_NUMBER", "8600 XXXX XXXX XXXX")
PAYMENT_CARD_HOLDER: str = os.getenv("PAYMENT_CARD_HOLDER", "Karta egasi F.I.O.")

# Kasalliklar ro'yxati rejimi (False = 10 ta kasallik, True = 3 ta umumlashgan tugma)
USE_SHORT_DISEASE_LIST: bool = os.getenv("USE_SHORT_DISEASE_LIST", "false").lower() == "true"

CONSULTATION_OFFER: str = (
    "💡 <i>«Bitta qabulning o‘zida siz va turmush o‘rtog‘ingiz birgalikda suhbatdan o‘tasiz, "
    "barcha eski analizlaringiz ko‘rib chiqiladi va Dr. Zarifa uyda bajarish uchun "
    "shaxsiy yo‘l xaritasi hamda mashqlarni qo‘lingizga aniq yozib beradi.»</i>"
)

# Tibbiy xavfsizlik va etika eslatmasi
SAFETY_NOTICE: str = (
    "⚠️ <b>Muhim tibbiy eslatma:</b>\n"
    "<i>Ushbu bot faqat qabulga yozilish va ma'lumot berish uchun xizmat qiladi. "
    "Bot orqali onlayn tashxis qo‘yilmaydi va dori-darmonlar tayinlanmaydi. "
    "Agar sizda o‘tkir kuchli og‘riq yoki to‘xtovsiz qon ketish kabi favqulodda holatlar kuzatilsa, "
    "darhol <b>103</b> tez tibbiy yordam xizmatiga murojaat qiling!</i>"
)
