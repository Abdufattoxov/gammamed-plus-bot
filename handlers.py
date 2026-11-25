import os
import re
from datetime import datetime
from aiogram import Router, F, Bot
from aiogram.filters import Command, CommandStart, CommandObject, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardRemove,
    FSInputFile
)

from config import (
    ADMIN_IDS,
    ADMIN_GROUP_ID,
    CLINIC_NAME,
    CLINIC_NAME_COMMON,
    DOCTOR_NAME,
    DOCTOR_TITLE,
    DOCTOR_SPECIALTY,
    CLINIC_ADDRESS,
    CLINIC_WORKING_HOURS,
    CONSULTATION_OFFER,
    SAFETY_NOTICE
)
import database
from states import AppointmentState, AnonymousQuestionState, AdminBroadcastState
from keyboards import (
    get_main_menu_kb,
    get_back_cancel_reply_kb,
    get_phone_request_kb,
    get_cancel_reply_kb,
    get_problems_inline_kb,
    generate_calendar_kb,
    get_time_slots_inline_kb,
    get_admin_appointment_kb,
    get_admin_panel_kb,
    get_services_info_inline_kb
)

router = Router()

# Eng ko'p uchraydigan 10 ta kasallik va boshqa muammolar
PROBLEM_TITLES = {
    "bepushtlik": "1. Bepushtlik (homila bo‘lmasligi)",
    "hayz_ogriq": "2. Hayz og‘riqlari va sikl buzilishi",
    "endometrioz": "3. Endometrioz va adenomioz",
    "polikistoz": "4. Tuxumdonlar polikistozi (SPKY)",
    "mioma": "5. Bachadon miomasi",
    "kista": "6. Tuxumdon kistalari",
    "eroziya": "7. Bachadon bo‘yni eroziyasi",
    "adneksit": "8. Shamollash va adneksit",
    "molochnitsa": "9. Molochnitsa va ajralmalar",
    "klimaks": "10. Klimaks va gormonal o‘zgarishlar",
    "boshqa_muammo": "Boshqa ginekologik kasalliklar",
    "farzand_yoq": "1. Bepushtlik (homila bo‘lmasligi)",
    "ikkalasi_ham": "Bepushtlik va hayz og‘riqlari"
}


# ==========================================
# 1. YORDAMCHI FUNKSIYALAR
# ==========================================
def clean_phone_number(text: str) -> str | None:
    """Telefon raqamini tozalash va O'zbekiston formatiga tekshirish"""
    digits = re.sub(r"\D", "", text)
    if len(digits) == 9:
        return f"+998{digits}"
    elif len(digits) == 12 and digits.startswith("998"):
        return f"+{digits}"
    elif len(digits) == 10 and digits.startswith("8"):
        return f"+998{digits[1:]}"
    elif len(digits) == 11 and digits.startswith("8998"):
        return f"+{digits[1:]}"
    return None


def format_uz_date(date_str: str) -> str:
    """Sanani o'zbekcha chiroyli matnga aylantirish (Masalan: 26-noyabr 2026 (Payshanba))"""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        weekdays = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]
        months = ["", "yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr"]
        return f"{dt.day}-{months[dt.month]} {dt.year} ({weekdays[dt.weekday()]})"
    except Exception:
        return date_str


def is_menu_navigation(text: str | None) -> bool:
    """Xabar asosiy menyu yoki bekor qilish tugmasi ekanligini aniqlash"""
    if not text:
        return False
    t = text.strip()
    keywords = [
        "Qabulga yozilish",
        "Xizmatlarimiz",
        "Xizmatlar va narxlar",
        "Shifokor haqida",
        "Manzil va ish vaqti",
        "Anonim savol",
        "Bekor qilish"
    ]
    return any(k in t for k in keywords)


# ==========================================
# 2. START VA DEEP-LINK VORONKASI
# ==========================================
@router.message(CommandStart(), StateFilter("*"))
async def cmd_start(message: Message, command: CommandObject, state: FSMContext):
    """
    Start buyrug'i.
    Agar /start bulungur_ads havolasi orqali kirilsa, asosiy menyusiz to'g'ridan-to'g'ri 1-bosqich boshlanadi.
    """
    await state.clear()

    # Foydalanuvchini bazaga kiritish
    user = message.from_user
    if user:
        await database.register_user(
            user_id=user.id,
            full_name=user.full_name,
            username=user.username
        )

    # 1. Target reklama (Deep-link: /start bulungur_ads)
    if command.args and "bulungur_ads" in command.args:
        await state.set_state(AppointmentState.problem)
        deep_link_text = (
            f"Assalomu alaykum va rahmatulloh! 🌸\n\n"
            f"<b>«{CLINIC_NAME}»</b> ({CLINIC_NAME_COMMON}) — {DOCTOR_TITLE} <b>{DOCTOR_NAME}</b> "
            f"qabuliga tezkor yozilish sahifasidasiz.\n\n"
            f"👇 <b>1-bosqich:</b> Sizni qaysi muammo ko‘proq bezovta qilmoqda? "
            f"Quyidagi ro‘yxatdan tanlang:"
        )
        await message.answer(
            text=deep_link_text,
            reply_markup=get_problems_inline_kb()
        )
        return

    # 2. Standart /start
    greeting_name = user.first_name if user else "muhtaram bemor"
    welcome_text = (
        f"Assalomu alaykum va rahmatulloh, hurmatli <b>{greeting_name}</b>! 🌸\n\n"
        f"<b>«{CLINIC_NAME}»</b> ({CLINIC_NAME_COMMON}) — {DOCTOR_TITLE} <b>{DOCTOR_NAME}</b>ning "
        f"rasmiy telegram botiga xush kelibsiz.\n\n"
        f"🩺 <b>Asosiy ixtisoslashuv yo‘nalishlarimiz:</b>\n"
        f"• Bepushtlik (farzand ko‘ra olmaslik, analizlar toza bo‘lsa ham homila bo‘lmasligi)\n"
        f"• Hayz oldi va hayz davridagi kuchli og‘riqlar\n"
        f"• Gormonal va psixosomatik muammolar\n\n"
        f"Quyidagi menyu orqali qabulga yozilishingiz yoki xizmatlarimiz bilan tanishishingiz mumkin:"
    )

    await message.answer(
        text=welcome_text,
        reply_markup=get_main_menu_kb()
    )


# ==========================================
# 3. UMUMIY BEKOR QILISH VA ASOSIY MENYUGA QAYTISH
# ==========================================
@router.message(F.text.func(lambda t: t and ("Bekor qilish" in t)), StateFilter("*"))
async def cancel_handler_text(message: Message, state: FSMContext):
    """Jarayonni matn orqali bekor qilish"""
    await state.clear()
    await message.answer(
        "Amaliyot bekor qilindi. Siz asosiy menyudasiz. Kerakli bo‘limni tanlang:",
        reply_markup=get_main_menu_kb()
    )


@router.callback_query(F.data == "action_cancel", StateFilter("*"))
async def cancel_handler_callback(callback: CallbackQuery, state: FSMContext):
    """Jarayonni inline tugma orqali bekor qilish"""
    await state.clear()
    await callback.answer()
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer(
        "Amaliyot bekor qilindi. Siz asosiy menyudasiz. Kerakli bo‘limni tanlang:",
        reply_markup=get_main_menu_kb()
    )


# ==========================================
# 4. MA'LUMOT BO'LIMLARI
# ==========================================
@router.message(F.text.func(lambda t: t and any(k in t for k in ["Xizmatlarimiz", "Xizmatlar"])), StateFilter("*"))
async def services_info_handler(message: Message, state: FSMContext):
    """Xizmatlarimiz bo'limi: kasalliklar va davolash yo'nalishlari"""
    await state.clear()
    text = (
        f"Dr. Zarifa 30 yillik chuqur amaliy tajriba hamda psixosomatik yondashuv asosida "
        f"quyidagi eng ko‘p uchraydigan kasalliklar va boshqa ginekalogik kasalliklarni muvaffaqiyatli davolaydi:\n\n"
        f"1️⃣ <b>Bepushtlik</b> — barcha analizlar toza bo‘lsa ham yillab homila bo‘lmasligi, psixogen va gormonal to‘siqlar;\n"
        f"2️⃣ <b>Hayz sikli buzilishi va kuchli og‘riqlar (dismenoreya)</b> — tartibsiz hayz, hayz oldi va paytidagi chidab bo‘lmas og‘riqlar;\n"
        f"3️⃣ <b>Endometrioz va adenomioz</b> — surunkali tos sohasidagi og‘riqlar va yallig‘lanishlar;\n"
        f"4️⃣ <b>Tuxumdonlar polikistozi sindromi (SPKY / PCOS)</b> — ovulyatsiyaning buzilishi, gormonal disbalans;\n"
        f"5️⃣ <b>Bachadon miomasi</b> — xavfsiz o‘smalar, og‘irlik va noqulaylik hissi;\n"
        f"6️⃣ <b>Tuxumdon kistalari</b> — follikulyar, sariq tana va boshqa turdagi kistalarni nazorat qilish hamda davolash;\n"
        f"7️⃣ <b>Bachadon bo‘yni eroziyasi va patologiyalari</b> — shilliq qavat zararlanishlarini tekshirish;\n"
        f"8️⃣ <b>Kichik tos a'zolari yallig‘lanish kasalliklari (adneksit, endometrit)</b> — shamollash va surunkali og‘riqlar;\n"
        f"9️⃣ <b>Kandidoz (molochnitsa), kolpit va vaginozlar</b> — qin mikroflorasi buzilishi, qichishish va noxush ajralmalar;\n"
        f"🔟 <b>Klimakterik sindrom va gormonal o‘zgarishlar</b> — qizib ketishlar, hissiy zo‘riqishlar va noxush alomatlar;\n\n"
        f"✨ <i>... va boshqa barcha ginekologik kasalliklar bo‘yicha professional yordam ko‘rsatiladi.</i>\n\n"
        f"🔍 Shuningdek, klinikada zamonaviy <b>UTT (UZI) tekshiruvi</b> va homiladorlikka tayyorgarlik ko‘rish xizmatlari mavjud.\n\n"
        f"💳 <b>Qabul narxi va batafsil ma'lumotlar qo‘ng‘iroq orqali aniqlashtiriladi.</b>\n\n"
        f"{SAFETY_NOTICE}"
    )
    await message.answer(
        text=text,
        reply_markup=get_services_info_inline_kb()
    )


@router.message(F.text.func(lambda t: t and ("Shifokor haqida" in t or "Shifokor" in t)), StateFilter("*"))
async def doctor_info_handler(message: Message, state: FSMContext):
    """Shifokor haqida ma'lumot va fotosurat"""
    await state.clear()
    caption_text = (
        f"👩‍⚕️ <b>Shifokor haqida:</b>\n\n"
        f"<b>{DOCTOR_NAME}</b> — {DOCTOR_TITLE}.\n\n"
        f"🩺 <b>Asosiy ixtisoslashuv yo‘nalishi:</b>\n"
        f"{DOCTOR_SPECIALTY}\n\n"
        f"🌿 <b>Davolash tamoyili:</b>\n"
        f"<i>«Biz ayollar salomatligiga butun tana va ruhiyat uyg‘unligida yondashamiz. "
        f"Har bir bemorimizga yuksak mehr, vazminlik va individual e'tibor ko‘rsatish — bosh maqsadimizdir.»</i>\n\n"
        f"{SAFETY_NOTICE}"
    )

    photo_path = "doctor_photo.jpg"
    if os.path.exists(photo_path):
        await message.answer_photo(
            photo=FSInputFile(photo_path),
            caption=caption_text,
            reply_markup=get_services_info_inline_kb()
        )
    else:
        await message.answer(
            text=caption_text,
            reply_markup=get_services_info_inline_kb()
        )


@router.message(F.text.func(lambda t: t and ("Manzil" in t or "ish vaqti" in t)), StateFilter("*"))
async def address_info_handler(message: Message, state: FSMContext):
    """Manzil va ish vaqti"""
    await state.clear()
    text = (
        f"📍 <b>«{CLINIC_NAME}» klinikasining manzili va ish tartibi:</b>\n\n"
        f"🏢 <b>Manzil va mo‘ljal:</b>\n"
        f"{CLINIC_ADDRESS}\n\n"
        f"🕒 <b>Ish vaqti:</b>\n"
        f"{CLINIC_WORKING_HOURS}\n\n"
        f"ℹ️ <i>Bemorlar Dr. Zarifa qabuliga navbatsiz va qulay vaqtda kirishlari uchun "
        f"oldindan bot orqali ariza qoldirish tavsiya etiladi.</i>\n\n"
        f"{SAFETY_NOTICE}"
    )
    await message.answer(
        text=text,
        reply_markup=get_services_info_inline_kb()
    )


@router.message(F.text.func(lambda t: t and ("bog‘lanish" in t or "bog'lanish" in t)), StateFilter("*"))
async def contact_fallback_handler(message: Message, state: FSMContext):
    """Eski bog'lanish tugmasi bosilganda xabar berish"""
    await state.clear()
    text = (
        f"ℹ️ <b>Qabulga yozilish tartibi:</b>\n\n"
        f"Hozirda kiruvchi qo‘ng‘iroqlarga javob beruvchi alohida telefon raqami ko‘rsatilmaydi — "
        f"bemorlar bot orqali ariza qoldiradi, o‘zimiz tez orada sizga qo‘ng‘iroq qilamiz.\n\n"
        f"Quyidagi tugma orqali arizangizni qoldirishingiz mumkin:"
    )
    await message.answer(text=text, reply_markup=get_services_info_inline_kb())


# ==========================================
# 5. ANONIM SAVOL BERISH OQIMI
# ==========================================
@router.message(F.text.func(lambda t: t and ("Anonim savol" in t)), StateFilter("*"))
async def anon_question_start(message: Message, state: FSMContext):
    """Anonim savol berishni boshlash"""
    await state.clear()
    await state.set_state(AnonymousQuestionState.waiting_for_question)
    text = (
        f"❓ <b>Shifokorga anonim savol yo‘llash</b>\n\n"
        f"Siz ayollar salomatligi yoki psixosomatika bo‘yicha o‘zingizni o‘ylantirayotgan "
        f"nozik savolingizni bevosita <b>{DOCTOR_NAME}</b>ga yuborishingiz mumkin.\n\n"
        f"🔒 <b>Maxfiylik kafolati:</b>\n"
        f"Savolingiz shifokorga shaxsiy ma'lumotlaringiz "
        f"<b>mutlaqo ko‘rsatilmagan holda</b>, butunlay anonim tarzda yetkaziladi.\n\n"
        f"{SAFETY_NOTICE}\n\n"
        f"✍️ <i>Savolingizni bitta xabarda batafsil yozib yuboring:</i>"
    )
    await message.answer(
        text=text,
        reply_markup=get_cancel_reply_kb()
    )


@router.message(AnonymousQuestionState.waiting_for_question, F.text)
async def anon_question_receive(message: Message, state: FSMContext, bot: Bot):
    """Anonim savolni qabul qilish va adminga yuborish"""
    if is_menu_navigation(message.text):
        await state.clear()
        if "Bekor qilish" in message.text:
            await message.answer("Savol yuborish bekor qilindi.", reply_markup=get_main_menu_kb())
            return

    question_text = message.text.strip()
    if len(question_text) < 10:
        await message.answer(
            "Iltimos, savolingizni biroz to‘liqroq bayon qiling (kamida 10 ta belgi).",
            reply_markup=get_cancel_reply_kb()
        )
        return

    user_id = message.from_user.id if message.from_user else 0
    question_id = await database.save_anonymous_question(user_id, question_text)
    await state.clear()

    reply_text = (
        f"🕊 <b>Savolingiz muvaffaqiyatli qabul qilindi!</b>\n\n"
        f"Savolingiz #{question_id} raqami bilan anonim tarzda shifokorga yetkazildi. "
        f"Dr. Zarifa bo‘sh vaqt topishi bilan savollarga umumiy maslahat tayyorlaydi.\n\n"
        f"Salomatligingizga befarq bo‘lmaganingiz uchun tashakkur!"
    )
    await message.answer(
        text=reply_text,
        reply_markup=get_main_menu_kb()
    )

    notify_text = (
        f"❓ <b>YANGI ANONIM SAVOL (#{question_id})</b>\n\n"
        f"📝 <b>Savol matni:</b>\n"
        f"<i>«{question_text}»</i>\n\n"
        f"⏰ <b>Vaqti:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
        f"🔒 <i>Yuboruvchi shaxsi anonim saqlangan.</i>"
    )

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(chat_id=admin_id, text=notify_text)
        except Exception:
            pass

    if ADMIN_GROUP_ID:
        try:
            await bot.send_message(chat_id=ADMIN_GROUP_ID, text=notify_text)
        except Exception:
            pass


# ==========================================
# 6. QABULGA YOZILISH OQIMI (FSM)
# ==========================================

# --- 1-BOSQICH: Muammoni tanlash ---
@router.message(F.text.func(lambda t: t and ("Qabulga yozilish" in t)), StateFilter("*"))
@router.callback_query(F.data == "start_appointment_flow", StateFilter("*"))
async def start_appointment_flow(event: Message | CallbackQuery, state: FSMContext):
    """Qabulga yozilishni boshlash — 1-bosqich: Muammoni tanlash"""
    await state.clear()
    await state.set_state(AppointmentState.problem)

    text = (
        f"📅 <b>Dr. Zarifa qabuliga yozilish</b>\n\n"
        f"👇 <b>1-bosqich:</b> Sizni qaysi muammo ko‘proq bezovta qilmoqda? "
        f"Quyidagi ro‘yxatdan tanlang:\n\n"
        f"{SAFETY_NOTICE}"
    )

    if isinstance(event, CallbackQuery):
        await event.answer()
        try:
            await event.message.delete()
        except Exception:
            pass
        await event.message.answer(
            text=text,
            reply_markup=get_problems_inline_kb()
        )
    else:
        await event.answer(
            text=text,
            reply_markup=get_problems_inline_kb()
        )


@router.callback_query(F.data.startswith("prob:"), AppointmentState.problem)
async def process_problem_selection(callback: CallbackQuery, state: FSMContext):
    """Muammo tanlanganda 2-bosqichga o'tish: Ism-familiya kiritish"""
    key = callback.data.split(":", 1)[1]
    problem_name = PROBLEM_TITLES.get(key, "Boshqa ginekologik kasalliklar")

    await state.update_data(problem=problem_name)
    await state.set_state(AppointmentState.patient_name)

    await callback.answer()
    try:
        await callback.message.delete()
    except Exception:
        pass

    text = (
        f"✅ <b>Tanlangan yo‘nalish:</b> {problem_name}\n\n"
        f"👤 <b>2-bosqich: Bemorning ism-familiyasi</b>\n\n"
        f"Iltimos, qabulga yozilayotgan bemorning to‘liq ism va familiyasini kiriting:\n"
        f"<i>(Masalan: Karimova Dilnoza)</i>"
    )
    await callback.message.answer(
        text=text,
        reply_markup=get_back_cancel_reply_kb()
    )


@router.message(AppointmentState.problem, F.text)
async def process_problem_text_fallback(message: Message, state: FSMContext):
    """1-bosqichda foydalanuvchi matn yozsa yo'naltirish"""
    if is_menu_navigation(message.text):
        await state.clear()
        if "Bekor qilish" in message.text:
            await message.answer("Qabulga yozilish bekor qilindi.", reply_markup=get_main_menu_kb())
        return

    await message.answer(
        "👇 Iltimos, yuqoridagi ro‘yxatdan o‘zingizga kerakli tugmani bosing "
        "yoki «❌ Bekor qilish» tugmasidan foydalaning:",
        reply_markup=get_problems_inline_kb()
    )


# --- 2-BOSQICH: Ism-familiya kiritish va orqaga qaytish ---
@router.message(AppointmentState.patient_name, F.text.func(lambda t: t and ("Orqaga" in t)))
async def back_from_name_to_problem(message: Message, state: FSMContext):
    """Ism kiritishdan muammo tanlashga qaytish"""
    await state.set_state(AppointmentState.problem)
    text = (
        f"👇 <b>1-bosqich:</b> Sizni qaysi muammo ko‘proq bezovta qilmoqda? "
        f"Quyidagi ro‘yxatdan tanlang:"
    )
    await message.answer(
        text=text,
        reply_markup=get_problems_inline_kb()
    )


@router.message(AppointmentState.patient_name, F.text)
async def process_patient_name(message: Message, state: FSMContext):
    """Bemor ismini qabul qilish va 3-bosqich: Telefon raqam so'rash"""
    name = message.text.strip()
    if is_menu_navigation(name):
        await state.clear()
        if "Bekor qilish" in name:
            await message.answer(
                "Qabulga yozilish bekor qilindi. Siz asosiy menyudasiz:",
                reply_markup=get_main_menu_kb()
            )
        return

    if len(name) < 3 or len(name) > 70:
        await message.answer(
            "Iltimos, haqiqiy ism va familiyangizni to‘liq kiriting (kamida 3 ta harf):",
            reply_markup=get_back_cancel_reply_kb()
        )
        return

    await state.update_data(patient_name=name)
    await state.set_state(AppointmentState.phone_number)

    text = (
        f"👤 <b>Bemor:</b> {name}\n\n"
        f"📱 <b>3-bosqich: Telefon raqamingiz</b>\n\n"
        f"Klinikamiz siz bilan bog‘lanib, qabulni tasdiqlashi uchun telefon raqamingizni kiriting:\n"
        f"<i>(Masalan: <code>90 123 45 67</code> yoki <code>+998901234567</code>)</i>"
    )
    await message.answer(
        text=text,
        reply_markup=get_phone_request_kb()
    )


# --- 3-BOSQICH: Telefon raqam kiritish va Kalendarni ko'rsatish ---
@router.message(AppointmentState.phone_number, F.text.func(lambda t: t and ("Orqaga" in t)))
async def back_from_phone_to_name(message: Message, state: FSMContext):
    """Telefon raqamdan ism kiritishga qaytish"""
    await state.set_state(AppointmentState.patient_name)
    await message.answer(
        "👤 <b>2-bosqich:</b> Iltimos, bemorning ism-familiyasini qaytadan kiriting:",
        reply_markup=get_back_cancel_reply_kb()
    )


@router.message(AppointmentState.phone_number, F.contact)
async def process_phone_contact(message: Message, state: FSMContext):
    """Telefon raqam kontakt orqali yuborilganda — kalendarga o'tish"""
    contact = message.contact
    phone = contact.phone_number
    if not phone.startswith("+"):
        phone = f"+{phone}"

    await proceed_to_calendar(message=message, state=state, phone_number=phone)


@router.message(AppointmentState.phone_number, F.text)
async def process_phone_text(message: Message, state: FSMContext):
    """Telefon raqam matn shaklida yozilganda — kalendarga o'tish"""
    if is_menu_navigation(message.text):
        await state.clear()
        if "Bekor qilish" in message.text:
            await message.answer(
                "Qabulga yozilish bekor qilindi. Siz asosiy menyudasiz:",
                reply_markup=get_main_menu_kb()
            )
        return

    phone = clean_phone_number(message.text)
    if not phone:
        err_text = (
            "Iltimos, telefon raqamingizni to‘g‘ri shaklda kiriting:\n"
            "<i>(Masalan: <code>90 123 45 67</code> yoki <code>+998901234567</code>)</i>"
        )
        await message.answer(
            text=err_text,
            reply_markup=get_phone_request_kb()
        )
        return

    await proceed_to_calendar(message=message, state=state, phone_number=phone)


async def proceed_to_calendar(message: Message, state: FSMContext, phone_number: str):
    """Telefon saqlanib, 4-bosqich (Kalendar) ochiladi"""
    await state.update_data(phone_number=phone_number)
    await state.set_state(AppointmentState.appointment_date)

    now = datetime.now()
    calendar_kb = generate_calendar_kb(year=now.year, month=now.month)

    text = (
        f"📞 <b>Telefon raqam:</b> {phone_number}\n\n"
        f"🗓 <b>4-bosqich: Qabul kunini tanlang</b>\n\n"
        f"Dr. Zarifa qabuliga qaysi kuni kelishni rejalashtirmoqdasiz? "
        f"Quyidagi kalendardan o‘zingizga qulay sanani tanlang:\n\n"
        f"<i>(Eslatma: Yakshanba — klinikamizda dam olish kuni)</i>"
    )

    await message.answer("Kalendar ochilmoqda...", reply_markup=get_cancel_reply_kb())
    await message.answer(text=text, reply_markup=calendar_kb)


# --- 4-BOSQICH: Kalendar orqali sanani tanlash ---
@router.callback_query(F.data.startswith("cal_nav:"), AppointmentState.appointment_date)
async def process_calendar_nav(callback: CallbackQuery):
    """Kalendarda oldingi/keyingi oylarga o'tish"""
    parts = callback.data.split(":")
    year = int(parts[1])
    month = int(parts[2])

    await callback.message.edit_reply_markup(
        reply_markup=generate_calendar_kb(year=year, month=month)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cal_ignore:"), AppointmentState.appointment_date)
async def process_calendar_ignore(callback: CallbackQuery):
    """O'tgan kun yoki yakshanba bosilganda tushuntirish"""
    reason = callback.data.split(":")[1]
    if reason == "sunday":
        await callback.answer("Yakshanba — klinikamizda dam olish kuni! Boshqa ish kunini tanlang.", show_alert=True)
    elif reason == "past":
        await callback.answer("O'tgan sanani tanlab bo'lmaydi.", show_alert=False)
    else:
        await callback.answer()


@router.callback_query(F.data == "cal_reopen", StateFilter("*"))
async def process_calendar_reopen(callback: CallbackQuery, state: FSMContext):
    """Qayta kalendarga qaytish"""
    await state.set_state(AppointmentState.appointment_date)
    now = datetime.now()
    calendar_kb = generate_calendar_kb(year=now.year, month=now.month)
    text = (
        f"🗓 <b>Qabul kunini qayta tanlang:</b>\n\n"
        f"Quyidagi kalendardan qulay sanani belgilang:"
    )
    await callback.message.edit_text(text=text, reply_markup=calendar_kb)
    await callback.answer()


@router.callback_query(F.data.startswith("cal_date:"), AppointmentState.appointment_date)
async def process_calendar_date(callback: CallbackQuery, state: FSMContext):
    """Kalendardan sana tanlanganda 5-bosqich (Vaqt tanlash) ga o'tish"""
    date_str = callback.data.split(":", 1)[1]
    formatted_date = format_uz_date(date_str)

    await state.update_data(appointment_date=date_str, formatted_date=formatted_date)
    await state.set_state(AppointmentState.appointment_time)

    text = (
        f"🗓 <b>Tanlangan sana:</b> {formatted_date}\n\n"
        f"⏰ <b>5-bosqich: Aniq qabul vaqtini tanlang</b>\n\n"
        f"Klinika ish vaqti: 09:00 — 17:00.\n"
        f"Quyidagi oraliqlardan o‘zingizga eng ma'qul vaqtni tanlang:"
    )

    await callback.message.edit_text(
        text=text,
        reply_markup=get_time_slots_inline_kb(date_str)
    )
    await callback.answer()


# --- 5-BOSQICH: Vaqt oralig'ini tanlash va Arizani yakunlash ---
@router.callback_query(F.data.startswith("slot:"), AppointmentState.appointment_time)
async def process_time_slot_selection(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Vaqt oralig'i tanlanganda darhol arizani bazaga saqlash va adminga yuborish"""
    parts = callback.data.split(":")
    date_str = parts[1]
    time_slot = parts[2]

    formatted_date = format_uz_date(date_str)
    full_appointment_time = f"{formatted_date} ({time_slot})"

    data = await state.get_data()
    user = callback.from_user
    user_id = user.id if user else 0
    username_str = f"@{user.username}" if user and user.username else "mavjud emas"

    patient_name = data.get("patient_name", "Noma'lum")
    problem = data.get("problem", "Boshqa ginekologik kasalliklar")
    phone_number = data.get("phone_number", "Ko'rsatilmadi")

    # 1. Bazaga to'liq saqlash
    app_id = await database.create_appointment(
        user_id=user_id,
        service=problem,
        patient_name=patient_name,
        phone_number=phone_number,
        appointment_time=full_appointment_time
    )
    await state.clear()

    await callback.answer("Qabul vaqti belgilandi!")
    try:
        await callback.message.delete()
    except Exception:
        pass

    # 2. Bemorga yakuniy tasdiq xabari
    success_text = (
        f"✅ <b>Arizangiz muvaffaqiyatli qabul qilindi!</b>\n\n"
        f"👤 <b>Bemor:</b> {patient_name}\n"
        f"🩺 <b>Yo‘nalish:</b> {problem}\n"
        f"📅 <b>Belgilangan qabul vaqti:</b> <b>{full_appointment_time}</b>\n\n"
        f"Tez orada klinikamiz ma'muri siz bilan bog‘lanib, qabulni tasdiqlaydi.\n\n"
        f"📍 <b>Manzil:</b> {CLINIC_ADDRESS}\n\n"
        f"<i>Qabulga kelayotganda barcha eski UTT va analiz qog‘ozlaringizni o‘zingiz bilan oling "
        f"(imkon bo‘lsa turmush o‘rtog‘ingiz bilan birga keling).</i>"
    )
    await callback.message.answer(
        text=success_text,
        reply_markup=get_main_menu_kb()
    )

    # 3. Adminlarga bildirishnoma
    clean_phone = re.sub(r"\D", "", phone_number)
    admin_notification = (
        f"🔔 <b>YANGI QABUL ARIZASI (#A-{app_id})</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Bemor:</b> {patient_name}\n"
        f"📞 <b>Telefon:</b> <a href='tel:+{clean_phone}'>{phone_number}</a>\n"
        f"🩺 <b>Tanlangan yo‘nalish:</b> {problem}\n"
        f"🗓 <b>Belgilangan vaqt:</b> <b>{full_appointment_time}</b>\n"
        f"🆔 <b>Telegram ID:</b> <code>{user_id}</code> ({username_str})\n"
        f"⏰ <b>Ariza vaqti:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📌 <b>Holati:</b> <i>Kutilmoqda</i>"
    )

    # Admin shaxsiy xabariga
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=admin_notification,
                reply_markup=get_admin_appointment_kb(app_id)
            )
        except Exception:
            pass

    # Admin guruhiga
    if ADMIN_GROUP_ID:
        try:
            await bot.send_message(
                chat_id=ADMIN_GROUP_ID,
                text=admin_notification,
                reply_markup=get_admin_appointment_kb(app_id)
            )
        except Exception:
            pass


# ==========================================
# 7. ADMIN ARIZA STATUSINI O'ZGARTIRISH
# ==========================================
@router.callback_query(F.data.startswith("adm_app:"))
async def process_admin_appointment_action(callback: CallbackQuery):
    """Admin ariza holatini o'zgartirishi"""
    parts = callback.data.split(":")
    app_id = int(parts[1])
    action = parts[2]

    admin_name = callback.from_user.first_name if callback.from_user else "Admin"

    if action == "accepted":
        status_text = f"✅ Qabul qilindi ({admin_name} tomonidan)"
        await database.update_appointment_status(app_id, "Qabul qilindi")
    elif action == "called":
        status_text = f"📞 Qo‘ng‘iroq qilindi ({admin_name} tomonidan)"
        await database.update_appointment_status(app_id, "Qo'ng'iroq qilindi")
    else:
        status_text = "Noma'lum"

    # HTML formatni to'liq saqlab qolish
    current_html = callback.message.html_text or ""
    if "📌 <b>Holati:</b>" in current_html:
        updated_text = re.sub(r"📌 <b>Holati:</b>.*", f"📌 <b>Holati:</b> <b>{status_text}</b>", current_html)
    elif "📌 Holati:" in current_html:
        updated_text = re.sub(r"📌 Holati:.*", f"📌 <b>Holati:</b> <b>{status_text}</b>", current_html)
    else:
        updated_text = f"{current_html}\n\n📌 <b>Holati:</b> <b>{status_text}</b>"

    try:
        await callback.message.edit_text(
            text=updated_text,
            reply_markup=get_admin_appointment_kb(app_id)
        )
    except Exception:
        pass

    await callback.answer(f"Ariza holati o'zgartirildi: {status_text}")


# ==========================================
# 8. ADMIN PANEL VA BUYRUQLAR
# ==========================================
@router.message(Command("admin"), StateFilter("*"))
async def cmd_admin_panel(message: Message, state: FSMContext):
    """Admin panelni ochish (Faqat ADMIN_IDS uchun)"""
    await state.clear()
    user_id = message.from_user.id if message.from_user else 0
    if user_id not in ADMIN_IDS:
        return

    text = (
        f"🔐 <b>«{CLINIC_NAME}» Boshqaruv Paneli (Admin)</b>\n\n"
        f"Xush kelibsiz! Ushbu bo‘lim orqali statistikani ko‘rishingiz, "
        f"bemorlar bazasini Excel fayl qilib yuklab olishingiz "
        f"hamda barcha foydalanuvchilarga xabar tarqatishingiz mumkin:"
    )
    await message.answer(text=text, reply_markup=get_admin_panel_kb())


@router.callback_query(F.data == "admin_stats")
async def admin_stats_callback(callback: CallbackQuery):
    """Statistikani ko'rsatish"""
    user_id = callback.from_user.id if callback.from_user else 0
    if user_id not in ADMIN_IDS:
        await callback.answer("Ruxsat berilmagan!", show_alert=True)
        return

    stats = await database.get_appointments_stats()
    text = (
        f"📊 <b>Klinika bot statistikasi:</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"👥 <b>Jami foydalanuvchilar:</b> {stats['total_users']} nafar\n"
        f"📅 <b>Bugungi arizalar:</b> {stats['today_appointments']} ta\n"
        f"⏳ <b>Kutilayotgan arizalar:</b> {stats['pending_appointments']} ta\n"
        f"📈 <b>Jami kelib tushgan arizalar:</b> {stats['total_appointments']} ta\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"⏰ <i>Yangilangan vaqt: {datetime.now().strftime('%d.%m.%Y %H:%M')}</i>"
    )
    await callback.message.edit_text(text=text, reply_markup=get_admin_panel_kb())
    await callback.answer()


@router.callback_query(F.data == "admin_export")
async def admin_export_callback(callback: CallbackQuery):
    """Bemorlar arizalar bazasini Excel fayl shaklida yuborish"""
    user_id = callback.from_user.id if callback.from_user else 0
    if user_id not in ADMIN_IDS:
        await callback.answer("Ruxsat berilmagan!", show_alert=True)
        return

    await callback.answer("Excel fayl tayyorlanmoqda...", show_alert=False)

    now_str = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"bemorlar_bazasi_{now_str}.xlsx"

    try:
        await database.export_appointments_to_excel(filename)
        doc = FSInputFile(filename, filename=filename)
        await callback.message.answer_document(
            document=doc,
            caption=f"📥 <b>Bemorlar arizalari bazasi ({datetime.now().strftime('%d.%m.%Y')})</b>\n\n"
                    f"Fayl muvaffaqiyatli yaratildi."
        )
    except Exception as e:
        await callback.message.answer(f"❌ Fayl yaratishda xatolik yuz berdi: {str(e)}")
    finally:
        if os.path.exists(filename):
            try:
                os.remove(filename)
            except Exception:
                pass


@router.callback_query(F.data == "admin_close")
async def admin_close_callback(callback: CallbackQuery):
    """Admin panelni yopish"""
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer("Admin panel yopildi.")


@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    """Xabar yuborishni boshlash"""
    user_id = callback.from_user.id if callback.from_user else 0
    if user_id not in ADMIN_IDS:
        await callback.answer("Ruxsat berilmagan!", show_alert=True)
        return

    await state.set_state(AdminBroadcastState.waiting_for_message)
    text = (
        f"📢 <b>Barcha foydalanuvchilarga xabar yuborish (Broadcast):</b>\n\n"
        f"Barcha bot a'zolariga yubormoqchi bo‘lgan xabaringizni (matn, rasm yoki post) "
        f"yuboring.\n\n"
        f"Bekor qilish uchun pastdagi tugmani bosing:"
    )
    await callback.message.answer(text=text, reply_markup=get_cancel_reply_kb())
    await callback.answer()


@router.message(AdminBroadcastState.waiting_for_message)
async def admin_broadcast_send(message: Message, state: FSMContext, bot: Bot):
    """Xabarni barcha foydalanuvchilarga tarqatish"""
    user_id = message.from_user.id if message.from_user else 0
    if user_id not in ADMIN_IDS:
        return

    if is_menu_navigation(message.text) and "Bekor qilish" in message.text:
        await state.clear()
        await message.answer("📢 Xabar tarqatish bekor qilindi.", reply_markup=get_main_menu_kb())
        return

    user_ids = await database.get_all_user_ids()
    await state.clear()

    status_msg = await message.answer(f"⏳ Xabar tarqatish boshlandi... Jami foydalanuvchilar: {len(user_ids)}")

    success_count = 0
    fail_count = 0

    for uid in user_ids:
        try:
            await message.copy_to(chat_id=uid)
            success_count += 1
        except Exception:
            fail_count += 1

    await status_msg.edit_text(
        f"📢 <b>Xabar tarqatish yakunlandi:</b>\n\n"
        f"✅ Muvaffaqiyatli yetkazildi: {success_count} ta\n"
        f"❌ Yetkazilmadi (bloklangan/o‘chirilgan): {fail_count} ta"
    )
    await message.answer("Siz asosiy menyudasiz:", reply_markup=get_main_menu_kb())
