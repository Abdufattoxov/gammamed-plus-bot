import os
import re
import asyncio
from datetime import datetime, timedelta, timezone
from aiogram import Router, F, Bot
from aiogram.filters import Command, CommandStart, CommandObject, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message,
    CallbackQuery,
    ReplyKeyboardRemove,
    FSInputFile,
    BotCommand,
    BotCommandScopeChat
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
    CONSULTATION_PRICE,
    TOTAL_CONSULTATION_PRICE,
    PREPAYMENT_BASE,
    CLINIC_REMAINING_AMOUNT,
    PAYMENT_CARD_NUMBER,
    PAYMENT_CARD_HOLDER,
    CONSULTATION_OFFER,
    SAFETY_NOTICE,
    GOOGLE_SHEET_URL
)
import database
import google_sheets
import meta_ads
from states import (
    AppointmentState,
    AdminBroadcastState,
    AdminManageState,
    PaymentReceiptState
)
from keyboards import (
    get_main_menu_kb,
    get_back_cancel_reply_kb,
    get_phone_request_kb,
    get_cancel_reply_kb,
    get_problems_inline_kb,
    generate_calendar_kb,
    get_time_slots_inline_kb,
    get_admin_appointment_kb,
    get_admin_reject_reasons_kb,
    get_client_receipt_kb,
    get_admin_receipt_check_kb,
    get_admin_panel_kb,
    get_admin_manage_kb,
    get_admin_perm_toggle_kb,
    get_admin_list_kb,
    get_db_clean_menu_kb,
    get_db_clean_confirm_kb,
    get_services_info_inline_kb
)

UZ_TZ = timezone(timedelta(hours=5))

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
        "Qabul narxi",
        "Xizmatlarimiz",
        "Xizmatlar va narxlar",
        "Shifokor haqida",
        "Manzil va ish vaqti",
        "Bekor qilish"
    ]
    return any(k in t for k in keywords)


async def track_event(event: Message | CallbackQuery, step_name: str):
    """Foydalanuvchi bosgan bo'lim yoki voronka bosqichini xavfsiz yozib borish"""
    try:
        user = event.from_user
        if user:
            await database.log_user_event(
                user_id=user.id,
                username=user.username,
                full_name=user.full_name,
                step_name=step_name
            )
    except Exception:
        pass


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
    await track_event(message, "start")

    # 1. Target reklama (Deep-link: /start bulungur_ads)
    if command.args and "bulungur_ads" in command.args:
        await state.set_state(AppointmentState.problem)
        await track_event(message, "step_1_disease")
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

    # 1.1 Instagram ChatPlace deep-link (/start ig_lead)
    if command.args and "ig_lead" in command.args:
        await message.answer(
            text=(
                "🌸 Assalomu alaykum! Instagram orqali qoldirgan arizangiz qabul qilindi. "
                "Tez orada ma’muriyatimiz sizga qo‘ng‘iroq qilib, Dr. Zarifa qabuliga aniq vaqtni "
                "belgilab beradi va shaxsiy tartib raqamingizni (№ 100+) rasmiylashtirib beradi."
            ),
            reply_markup=get_main_menu_kb()
        )
        return

    # 1.2 Instagram/ChatPlace mijozlari uchun shaxsiy to'lov havolasi (/start pay_<app_id>)
    if command.args and command.args.startswith("pay_"):
        app_id_str = command.args[4:].strip()
        if app_id_str.isdigit():
            app_id = int(app_id_str)
            app = await database.get_appointment_by_id(app_id)
            if not app:
                await message.answer("❌ Uzr, ushbu ariza topilmadi.", reply_markup=get_main_menu_kb())
                return
            if user and not app.get("user_id"):
                await database.link_appointment_user_id(app_id, user.id)
            if app.get("payment_status") == "paid":
                await message.answer(
                    f"✅ To‘lovingiz allaqachon tasdiqlangan! Sizning tartib raqamingiz: <b>№ {app.get('client_number')}</b>",
                    reply_markup=get_main_menu_kb()
                )
                return
            prepay = app.get("prepayment_amount") or (PREPAYMENT_BASE + (app_id % 99) + 1)
            remaining = CLINIC_REMAINING_AMOUNT
            if not app.get("prepayment_amount"):
                await database.set_appointment_prepayment(app_id, prepay, remaining)
            client_msg = (
                f"✅ <b>Qabulga yozilish tasdiqlandi!</b>\n\n"
                f"Joyingizni boshqa bemorga berib yubormasligimiz uchun oldindan to‘lovni quyidagi kartaga o‘tkazing:\n"
                f"💳 <b>Karta raqami:</b> <code>{PAYMENT_CARD_NUMBER}</code> ({PAYMENT_CARD_HOLDER})\n"
                f"💰 <b>Oldindan to‘lov (aniq summa):</b> <b>{_fmt_money(prepay)} so‘m</b> <i>(iltimos, aynan shu summani o‘tkazing)</i>\n"
                f"🏥 <b>Klinikada to‘lanadigan qoldiq:</b> <b>{_fmt_money(remaining)} so‘m</b>\n\n"
                f"👇 To‘lov qilgach, pastdagi tugmani bosib chek rasmini yuboring!"
            )
            await message.answer(
                text=client_msg,
                reply_markup=get_client_receipt_kb(app_id)
            )
            return

    # 2. Standart /start
    greeting_name = user.first_name if user else "muhtaram bemor"
    cta_block = (
        f"👇 <b>Dr. Zarifa qabuliga yozilish uchun pastdagi «📅 Qabulga yozilish» tugmasini bosing!</b>\n"
        f"<i>(Agar avval qabul narxi va ichiga kiruvchi 4 ta xizmat bilan tanishmoqchi bo‘lsangiz, «💰 Qabul narxi» tugmasini bosing.)</i>"
    )
    welcome_text = (
        f"Assalomu alaykum va rahmatulloh, hurmatli <b>{greeting_name}</b>! 🌸\n\n"
        f"{cta_block}\n\n"
        f"<b>«{CLINIC_NAME}»</b> ({CLINIC_NAME_COMMON}) — {DOCTOR_TITLE} <b>{DOCTOR_NAME}</b>ning "
        f"rasmiy telegram botiga xush kelibsiz.\n\n"
        f"🩺 <b>Asosiy ixtisoslashuv yo‘nalishlarimiz:</b>\n"
        f"• Bepushtlik (farzand ko‘ra olmaslik, analizlar toza bo‘lsa ham homila bo‘lmasligi)\n"
        f"• Hayz oldi va hayz davridagi kuchli og‘riqlar\n"
        f"• Gormonal va psixosomatik muammolar\n\n"
        f"{cta_block}"
    )

    await message.answer(
        text="🌸 <b>Asosiy menyu faollashtirildi:</b>",
        reply_markup=get_main_menu_kb()
    )
    await message.answer(
        text=welcome_text,
        reply_markup=get_services_info_inline_kb("📅 Hoziroq qabulga yozilish")
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
@router.message(F.text.func(lambda t: t and ("Qabul narxi" in t)), StateFilter("*"))
async def price_info_handler(message: Message, state: FSMContext):
    """Qabul narxi bo'limi: Hormozi Value Stack taklifi"""
    await state.clear()
    await track_event(message, "menu_price")
    text = (
        f"💰 <b>Birlamchi chuqur qabul narxi: {CONSULTATION_PRICE}</b>\n"
        f"<i>(Qabulga yozilish jarayonini boshlash uchun qabulga yozilish tugmasini bosing)</i>\n\n"
        f"<b>Bu narxning ichiga nimalar kiradi (bitta qabulda 4 ta xizmat):</b>\n"
        f"1️⃣ <b>Er-xotin birgalikdagi chuqur suhbat</b> — bitta narxning o‘zida turmush o‘rtog‘ingiz bilan birga kirasiz;\n"
        f"2️⃣ <b>Eski analiz va UTT qog‘ozlarining to‘liq auditi</b> — Dr. Zarifa (30 yil tajriba) barcha qog‘ozlaringizni ko‘rib, keraksiz dorilar va ortiqcha xarajatlardan himoya qiladi;\n"
        f"3️⃣ <b>To‘liq tuzalishga qaratilgan shaxsiy mashqlar kompleksi</b> — og‘riq va bachadon spazmini dorisiz yechuvchi maxsus mashqlar qo‘lingizga yozib va tushuntirib beriladi;\n"
        f"4️⃣ <b>24 soatlik individual kun tartibi xaritasi</b> — uyg‘onishdan uyqugacha bo‘lgan soatma-soat tiklanish rejasi aniq yozib va tushuntirib beriladi.\n\n"
        f"⚠️ Haftalik qabul o‘rinlari cheklangan. Qabulga yozilish uchun pastdagi tugmani bosing 👇"
    )
    await message.answer(
        text=text,
        reply_markup=get_services_info_inline_kb("📅 Hoziroq qabulga yozilish")
    )


@router.message(F.text.func(lambda t: t and any(k in t for k in ["Xizmatlarimiz", "Xizmatlar"])), StateFilter("*"))
async def services_info_handler(message: Message, state: FSMContext):
    """Xizmatlarimiz bo'limi: kasalliklar va davolash yo'nalishlari"""
    await state.clear()
    await track_event(message, "menu_services")
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
    await track_event(message, "menu_doctor")
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
    await track_event(message, "menu_location")
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
# 6. QABULGA YOZILISH OQIMI (FSM)
# ==========================================

# --- 1-BOSQICH: Muammoni tanlash ---
@router.message(F.text.func(lambda t: t and ("Qabulga yozilish" in t)), StateFilter("*"))
@router.callback_query(F.data == "start_appointment_flow", StateFilter("*"))
async def start_appointment_flow(event: Message | CallbackQuery, state: FSMContext):
    """Qabulga yozilishni boshlash — 1-bosqich: Muammoni tanlash"""
    await state.clear()
    await state.set_state(AppointmentState.problem)
    if isinstance(event, Message):
        await track_event(event, "menu_booking")
    await track_event(event, "step_1_disease")

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
    await track_event(callback, "step_2_name")

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
    await track_event(message, "step_3_phone")

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
    await track_event(message, "step_4_date")

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

    try:
        await callback.message.edit_reply_markup(
            reply_markup=generate_calendar_kb(year=year, month=month)
        )
    except Exception:
        pass
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
    await track_event(callback, "step_5_time")

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
        appointment_time=full_appointment_time,
        appointment_date_iso=date_str,
        appointment_slot=time_slot
    )
    await state.clear()
    await track_event(callback, "step_6_confirmed")

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

    # Admin shaxsiy xabariga (ariza ko'rish huquqi bor barcha adminlarga)
    appointment_admins = await database.get_admins_with_permission("can_manage_appointments")
    for admin_id in appointment_admins:
        try:
            sent_msg = await bot.send_message(
                chat_id=admin_id,
                text=admin_notification,
                reply_markup=get_admin_appointment_kb(app_id, "Kutilmoqda")
            )
            await database.save_admin_appointment_message(
                appointment_id=app_id,
                chat_id=sent_msg.chat.id,
                message_id=sent_msg.message_id
            )
        except Exception:
            pass

    # Admin guruhiga
    if ADMIN_GROUP_ID:
        try:
            sent_msg = await bot.send_message(
                chat_id=ADMIN_GROUP_ID,
                text=admin_notification,
                reply_markup=get_admin_appointment_kb(app_id, "Kutilmoqda")
            )
            await database.save_admin_appointment_message(
                appointment_id=app_id,
                chat_id=sent_msg.chat.id,
                message_id=sent_msg.message_id
            )
        except Exception:
            pass

    # 4. Google Sheets'ga avtomatik yuborish (fondagi mustaqil vazifa)
    lead_payload = {
        "id": app_id,
        "date": datetime.now().strftime("%d.%m.%Y %H:%M"),
        "patient_name": patient_name,
        "phone_number": phone_number,
        "service": problem,
        "appointment_time": full_appointment_time,
        "status": "Kutilmoqda",
        "user_id": user_id
    }
    asyncio.create_task(google_sheets.append_lead_to_google_sheet(lead_payload))
    asyncio.create_task(send_excel_backup_to_admins(bot, app_id))


async def send_excel_backup_to_admins(bot: Bot, app_id: int):
    """Render.com da baza yo'qolmasligi uchun har yangi arizada adminlarga Excel zaxira faylini yuborish"""
    filename = f"bemorlar_bazasi_{app_id}.xlsx"
    try:
        await database.export_appointments_to_excel(filename)
        for admin_id in ADMIN_IDS:
            try:
                doc = FSInputFile(filename, filename="bemorlar_bazasi.xlsx")
                await bot.send_document(
                    chat_id=admin_id,
                    document=doc,
                    caption=f"💾 <b>Zaxira nusxa (#A-{app_id})</b> — Bemorlar bazasi (Excel)"
                )
            except Exception:
                pass
    except Exception:
        pass
    finally:
        if os.path.exists(filename):
            try:
                os.remove(filename)
            except Exception:
                pass


# ==========================================
# 7. MIJOZ TASDIQLASH, TO'LOV CHEKI VA RAQAM BERISH
# ==========================================
def _fmt_money(amount: int) -> str:
    """Pul miqdorini bo'sh joylar bilan chiroyli formatlash (30 014)"""
    return f"{int(amount):,}".replace(",", " ")


async def _update_all_admin_appointment_msgs(bot: Bot, app_id: int, status_line: str, reply_markup=None, source_html: str = ""):
    """Arizaga tegishli barcha admin xabarlaridagi holat qatorini HTML ni buzmasdan yangilash"""
    admin_messages = await database.get_admin_appointment_messages(app_id)
    if not admin_messages:
        return

    base_html = source_html
    if not base_html:
        app = await database.get_appointment_by_id(app_id)
        if not app:
            return
        clean_phone = re.sub(r"\D", "", app.get("phone_number") or "")
        base_html = (
            f"🔔 <b>QABUL ARIZASI (#A-{app_id})</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>Bemor:</b> {app.get('patient_name', '')}\n"
            f"📞 <b>Telefon:</b> <a href='tel:+{clean_phone}'>{app.get('phone_number', '')}</a>\n"
            f"🩺 <b>Yo‘nalish:</b> {app.get('service', '')}\n"
            f"🗓 <b>Vaqt:</b> <b>{app.get('notes', '')}</b>\n"
            f"🆔 <b>Telegram ID:</b> <code>{app.get('user_id', '')}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"📌 <b>Holati:</b> <i>Kutilmoqda</i>"
        )

    if "📌 <b>Holati:</b>" in base_html:
        updated_text = re.sub(r"📌 <b>Holati:</b>.*", f"📌 <b>Holati:</b> <b>{status_line}</b>", base_html, flags=re.DOTALL)
    elif "📌 Holati:" in base_html:
        updated_text = re.sub(r"📌 Holati:.*", f"📌 <b>Holati:</b> <b>{status_line}</b>", base_html, flags=re.DOTALL)
    else:
        updated_text = f"{base_html}\n\n📌 <b>Holati:</b> <b>{status_line}</b>"

    for m in admin_messages:
        try:
            await bot.edit_message_text(
                chat_id=m["chat_id"],
                message_id=m["message_id"],
                text=updated_text,
                reply_markup=reply_markup
            )
        except Exception:
            pass


async def send_reception_list(bot: Bot, target_chat_id: int, target_dates: list[str], title_label: str):
    """Tasdiqlangan (paid) mijozlar ro'yxatini matn + Excel (.xlsx) ko'rinishida yuborish"""
    rows = await database.get_paid_appointments_for_dates(target_dates)
    if not rows:
        await bot.send_message(
            chat_id=target_chat_id,
            text=f"📋 <b>{title_label}</b>\n\n<i>Hozircha tasdiqlangan (to‘lov qilgan) mijozlar yo‘q.</i>"
        )
        return

    lines = [f"📋 <b>{title_label} ({len(rows)} nafar):</b>\n━━━━━━━━━━━━━━━━━━━"]
    for r in rows:
        num = r.get("client_number") or "-"
        name = r.get("patient_name") or "Noma'lum"
        phone = r.get("phone_number") or ""
        date_iso = r.get("appointment_date_iso") or ""
        slot = r.get("appointment_slot") or ""
        rem = _fmt_money(CLINIC_REMAINING_AMOUNT)
        lines.append(
            f"🎫 <b>№ {num}</b> | {name} | <code>{phone}</code>\n"
            f"   🕒 {date_iso} ({slot}) | 💵 Resepshnda olinadi: <b>{rem} so‘m</b>"
        )

    await bot.send_message(chat_id=target_chat_id, text="\n".join(lines))

    filename = f"bemorlar_bazasi_{target_chat_id}_{datetime.now(UZ_TZ).strftime('%Y%m%d_%H%M')}.xlsx"
    try:
        await database.export_appointments_to_excel(filename)
        doc = FSInputFile(filename, filename="bemorlar_bazasi.xlsx")
        await bot.send_document(
            chat_id=target_chat_id,
            document=doc,
            caption=f"📥 <b>{title_label}</b> — 2 sahifali Excel ro‘yxat"
        )
    except Exception:
        pass
    finally:
        if os.path.exists(filename):
            try:
                os.remove(filename)
            except Exception:
                pass


REJECT_REASONS = {
    "not_answered": "📵 Ko‘tarmadi",
    "expensive": "💰 Narx qimmat dedi",
    "thinking": "🤔 O‘ylab ko‘radi",
    "mistake": "❌ Adashib bosgan",
}


@router.callback_query(F.data.startswith("adm_lead:"))
async def process_admin_lead_decision(callback: CallbackQuery, bot: Bot):
    """Admin ariza bo'yicha 'Mijoz bo'ldi' yoki 'Mijoz bo'lmadi' tugmasini bosganda"""
    user_id = callback.from_user.id if callback.from_user else 0
    perms = await database.get_admin_permissions(user_id)
    if not perms or not perms.get("can_manage_appointments"):
        return

    _, app_id_str, action = callback.data.split(":")
    app_id = int(app_id_str)
    app = await database.get_appointment_by_id(app_id)
    if not app:
        await callback.answer("Ariza topilmadi.", show_alert=True)
        return

    if action == "reject":
        await callback.answer()
        try:
            await callback.message.edit_reply_markup(reply_markup=get_admin_reject_reasons_kb(app_id))
        except Exception:
            pass
        return

    if action == "accept":
        if app.get("payment_status") == "paid":
            await callback.answer(f"Bu mijoz allaqachon tasdiqlangan (№ {app.get('client_number')})!", show_alert=True)
            return

        prepay = PREPAYMENT_BASE + (app_id % 99) + 1
        remaining = CLINIC_REMAINING_AMOUNT
        await database.set_appointment_prepayment(app_id, prepay, remaining)

        status_line = f"🟡 Mijoz rozi bo‘ldi — {_fmt_money(prepay)} so‘m chek kutilmoqda"
        await _update_all_admin_appointment_msgs(
            bot=bot,
            app_id=app_id,
            status_line=status_line,
            reply_markup=None,
            source_html=callback.message.html_text or ""
        )

        # Agar ariza Instagram/ChatPlace dan kelgan bo'lib user_id bog'lanmagan bo'lsa, adminga tayyor bot linkini ko'rsatamiz
        if not app.get("user_id"):
            bot_info = await bot.get_me()
            pay_link = f"https://t.me/{bot_info.username}?start=pay_{app_id}"
            await callback.message.answer(
                text=(
                    f"📲 <b>Instagram/ChatPlace mijoziga yuborish uchun to‘lov havolasi (#A-{app_id}):</b>\n\n"
                    f"👤 {html.escape(app.get('patient_name', ''))} | 💰 Summa: <b>{_fmt_money(prepay)} so‘m</b>\n"
                    f"🔗 <code>{pay_link}</code>\n\n"
                    f"<i>Mijoz ushbu havolani bosishi bilan unga karta raqami va chek yuborish tugmasi chiqadi.</i>"
                )
            )
            await callback.answer("To‘lov havolasi tayyorlandi!")
            return

        # Mijozga avtomatik karta va unikal summa xabarini yuborish
        client_msg = (
            f"✅ <b>Qabulga yozilish tasdiqlandi!</b>\n\n"
            f"Joyingizni boshqa bemorga berib yubormasligimiz uchun oldindan to‘lovni quyidagi kartaga o‘tkazing:\n"
            f"💳 <b>Karta raqami:</b> <code>{PAYMENT_CARD_NUMBER}</code> ({PAYMENT_CARD_HOLDER})\n"
            f"💰 <b>Oldindan to‘lov (aniq summa):</b> <b>{_fmt_money(prepay)} so‘m</b> <i>(iltimos, aynan shu summani o‘tkazing)</i>\n"
            f"🏥 <b>Klinikada to‘lanadigan qoldiq:</b> <b>{_fmt_money(remaining)} so‘m</b>\n\n"
            f"👇 To‘lov qilgach, pastdagi tugmani bosib chek rasmini yuboring!"
        )
        try:
            await bot.send_message(
                chat_id=app["user_id"],
                text=client_msg,
                reply_markup=get_client_receipt_kb(app_id)
            )
            await callback.answer(f"Mijozga {_fmt_money(prepay)} so‘m to‘lov xabari yuborildi!")
        except Exception:
            await callback.answer("⚠️ Mijozga xabar yuborib bo‘lmadi (botni bloklagan bo‘lishi mumkin).", show_alert=True)


@router.callback_query(F.data.startswith("adm_rej:"))
async def process_admin_reject_reason(callback: CallbackQuery, bot: Bot):
    """Admin 'Mijoz bo'lmadi' sababini tanlaganda"""
    user_id = callback.from_user.id if callback.from_user else 0
    perms = await database.get_admin_permissions(user_id)
    if not perms or not perms.get("can_manage_appointments"):
        return

    _, app_id_str, reason_code = callback.data.split(":")
    app_id = int(app_id_str)

    if reason_code == "back":
        await callback.answer()
        try:
            await callback.message.edit_reply_markup(reply_markup=get_admin_appointment_kb(app_id))
        except Exception:
            pass
        return

    reason_text = REJECT_REASONS.get(reason_code, "Rad etildi")
    await database.reject_appointment(app_id, reason_text)

    status_line = f"🔴 Mijoz bo‘lmadi | Sabab: {reason_text}"
    await _update_all_admin_appointment_msgs(
        bot=bot,
        app_id=app_id,
        status_line=status_line,
        reply_markup=None,
        source_html=callback.message.html_text or ""
    )
    await callback.answer(f"Sabab saqlandi: {reason_text}")


@router.callback_query(F.data.startswith("send_receipt:"))
async def start_receipt_upload(callback: CallbackQuery, state: FSMContext):
    """Mijoz '📸 To'lov chekini yuborish' tugmasini bosganda"""
    app_id = int(callback.data.split(":", 1)[1])
    app = await database.get_appointment_by_id(app_id)
    if not app:
        await callback.answer("Ariza topilmadi.", show_alert=True)
        return
    if app.get("payment_status") == "paid":
        await callback.answer("To‘lovingiz allaqachon tasdiqlangan!", show_alert=True)
        return

    await state.set_state(PaymentReceiptState.waiting_for_receipt)
    await state.update_data(receipt_app_id=app_id)
    await callback.answer()
    prepay = app.get("prepayment_amount") or PREPAYMENT_BASE
    await callback.message.answer(
        f"📸 <b>To‘lov cheki skrinshotini (rasmini) yuboring:</b>\n\n"
        f"💰 Kutilayotgan aniq summa: <b>{_fmt_money(prepay)} so‘m</b>\n"
        f"<i>(Chekni rasm yoki PDF fayl ko‘rinishida shu yerga tashlang)</i>",
        reply_markup=get_cancel_reply_kb()
    )


@router.message(PaymentReceiptState.waiting_for_receipt, F.text)
async def receipt_text_warning(message: Message, state: FSMContext):
    """Chek kutilayotganda mijoz rasm o'rniga matn yozsa"""
    if is_menu_navigation(message.text):
        await state.clear()
        if "Bekor qilish" in message.text:
            await message.answer("Jarayon bekor qilindi.", reply_markup=get_main_menu_kb())
        return
    await message.answer("⚠️ Iltimos, to‘lov chekining skrinshotini (rasmini) yuboring.")


@router.message(PaymentReceiptState.waiting_for_receipt, F.photo | F.document)
async def process_receipt_in_state(message: Message, state: FSMContext, bot: Bot):
    """FSM holatida chek rasm/PDF qabul qilish"""
    data = await state.get_data()
    app_id = data.get("receipt_app_id")
    await _handle_receipt_submission(message, state, bot, app_id)


@router.message(F.photo | F.document)
async def process_receipt_direct_fallback(message: Message, state: FSMContext, bot: Bot):
    """Mijoz tugmani bosmasdan (yoki server restartdan keyin) to'g'ridan-to'g'ri chek tashlasa"""
    user_id = message.from_user.id if message.from_user else 0
    app = await database.get_waiting_receipt_appointment_by_user(user_id)
    if not app:
        return
    await _handle_receipt_submission(message, state, bot, app["id"])


async def _handle_receipt_submission(message: Message, state: FSMContext, bot: Bot, app_id: int | None):
    """Chek rasmi yoki PDF ni tekshirish, dublikatdan himoyalash va adminlarga yuborish"""
    user_id = message.from_user.id if message.from_user else 0
    app = await database.get_appointment_by_id(app_id) if app_id else await database.get_waiting_receipt_appointment_by_user(user_id)
    if not app:
        await state.clear()
        return

    if app.get("payment_status") == "paid":
        await state.clear()
        await message.answer(
            f"✅ Sizning to‘lovingiz allaqachon tasdiqlangan (Tartib raqamingiz: <b>№ {app.get('client_number')}</b>).",
            reply_markup=get_main_menu_kb()
        )
        return

    if message.photo:
        file_id = message.photo[-1].file_id
        file_unique_id = message.photo[-1].file_unique_id
        is_photo = True
    elif message.document:
        file_id = message.document.file_id
        file_unique_id = message.document.file_unique_id
        is_photo = False
    else:
        await message.answer("⚠️ Iltimos, to‘lov chekining skrinshotini (rasmini) yuboring.")
        return

    if await database.is_receipt_used(file_unique_id):
        await message.answer("❌ Bu chek avval yuborilgan! Iltimos, yangi to‘lov chekini yuboring.")
        return

    await database.save_appointment_receipt(app["id"], file_id, file_unique_id)
    await state.clear()

    # O'zbekiston vaqti (UTC+5) bo'yicha xotirjam qiluvchi javob
    now_uz = datetime.now(UZ_TZ)
    if 8 <= now_uz.hour < 20:
        calm_text = (
            "⏳ <b>Chekingiz muvaffaqiyatli qabul qilindi!</b>\n\n"
            "To‘lov haqiqiyligi ma’muriyat tomonidan inson qo‘li bilan tekshirilib, "
            "<b>tez orada</b> tasdiqlanadi. Xavotir olmang, tasdiqlanishi bilan sizga "
            "shaxsiy tartib raqamingiz va rasmiy chiptangiz yuboriladi."
        )
    else:
        calm_text = (
            "🌙 <b>Chekingiz muvaffaqiyatli qabul qilindi!</b>\n\n"
            "Hozir ish vaqti yakunlangani sababli, chekingiz <b>ertaga ertalab soat 08:30 da</b> "
            "ma’muriyat tomonidan inson qo‘li bilan tekshirilib tasdiqlanadi. Xavotir olmang, "
            "joyingiz band qilindi — ertaga ertalab sizga shaxsiy tartib raqamingiz yuboriladi."
        )

    await message.answer(text=calm_text, reply_markup=get_main_menu_kb())

    prepay = app.get("prepayment_amount") or PREPAYMENT_BASE
    clean_phone = re.sub(r"\D", "", app.get("phone_number") or "")
    admin_caption = (
        f"💳 <b>YANGI TO‘LOV CHEKI (#A-{app['id']})</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Bemor:</b> {app.get('patient_name', '')}\n"
        f"📞 <b>Telefon:</b> <a href='tel:+{clean_phone}'>{app.get('phone_number', '')}</a>\n"
        f"🗓 <b>Qabul vaqti:</b> {app.get('notes', '')}\n"
        f"💰 <b>Kutilayotgan unikal summa:</b> <b>{_fmt_money(prepay)} so‘m</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"<i>Chekdagi summani tekshirib tasdiqlang:</i>"
    )

    target_admins = await database.get_admins_with_permission("can_manage_appointments")
    kb = get_admin_receipt_check_kb(app["id"])

    for adm_id in target_admins:
        try:
            if is_photo:
                sent = await bot.send_photo(chat_id=adm_id, photo=file_id, caption=admin_caption, reply_markup=kb)
            else:
                sent = await bot.send_document(chat_id=adm_id, document=file_id, caption=admin_caption, reply_markup=kb)
            await database.save_admin_receipt_message(app["id"], sent.chat.id, sent.message_id, is_media=True)
        except Exception:
            pass

    if ADMIN_GROUP_ID:
        try:
            if is_photo:
                sent = await bot.send_photo(chat_id=ADMIN_GROUP_ID, photo=file_id, caption=admin_caption, reply_markup=kb)
            else:
                sent = await bot.send_document(chat_id=ADMIN_GROUP_ID, document=file_id, caption=admin_caption, reply_markup=kb)
            await database.save_admin_receipt_message(app["id"], sent.chat.id, sent.message_id, is_media=True)
        except Exception:
            pass


@router.callback_query(F.data.startswith("adm_pay:"))
async def process_admin_payment_verification(callback: CallbackQuery, bot: Bot):
    """Admin chekni tasdiqlashi ('✅ Chek haqiqiy') yoki rad etishi ('❌ Chek xato')"""
    user_id = callback.from_user.id if callback.from_user else 0
    perms = await database.get_admin_permissions(user_id)
    if not perms or not perms.get("can_manage_appointments"):
        return

    _, app_id_str, action = callback.data.split(":")
    app_id = int(app_id_str)
    app = await database.get_appointment_by_id(app_id)
    if not app:
        await callback.answer("Ariza topilmadi.", show_alert=True)
        return

    prepay = app.get("prepayment_amount") or PREPAYMENT_BASE
    remaining = app.get("remaining_amount") or (TOTAL_CONSULTATION_PRICE - prepay)
    admin_msgs = await database.get_admin_receipt_messages(app_id)

    if action == "reject":
        await database.set_appointment_receipt_retry(app_id)
        try:
            await bot.send_message(
                chat_id=app["user_id"],
                text=(
                    f"⚠️ Yuborgan chekingiz tasdiqlanmadi (summa mos kelmadi yoki chek noaniq).\n\n"
                    f"Iltimos, <b>{_fmt_money(prepay)} so‘m</b> to‘lov chekini qaytadan yuboring."
                ),
                reply_markup=get_client_receipt_kb(app_id)
            )
        except Exception:
            pass

        reject_caption = (
            f"❌ <b>Chek rad etildi — qayta so‘raldi (#A-{app_id})</b>\n"
            f"👤 {app.get('patient_name', '')} | Kutilgan: <b>{_fmt_money(prepay)} so‘m</b>"
        )
        for m in admin_msgs:
            try:
                await bot.edit_message_caption(
                    chat_id=m["chat_id"],
                    message_id=m["message_id"],
                    caption=reject_caption,
                    reply_markup=None
                )
            except Exception:
                pass
        await callback.answer("Chek rad etildi va mijozdan qayta so‘raldi.")
        return

    if action == "approve":
        if app.get("payment_status") == "paid" and app.get("client_number") is not None:
            await callback.answer(f"Allaqachon tasdiqlangan (№ {app.get('client_number')})!", show_alert=True)
            return
        client_number = await database.approve_appointment_payment(app_id)

        date_disp = format_uz_date(app.get("appointment_date_iso") or "") if app.get("appointment_date_iso") else (app.get("notes") or "")
        time_disp = app.get("appointment_slot") or ""
        when_str = f"{date_disp} | {time_disp}".strip(" |")

        ticket_text = (
            f"🎉 <b>XUSHXABAR! To‘lovingiz tasdiqlandi, siz Dr. Zarifa qabuliga rasman yozildingiz!</b>\n\n"
            f"🎫 <b>Sizning tartib raqamingiz: № {client_number}</b>\n"
            f"📅 <b>Belgilangan kun va vaqt:</b> {when_str}\n"
            f"🏥 <b>Manzil:</b> Bulung‘ur tumani, «Yulduz» kinoteatri yonidagi <b>Gammamed Plus</b> klinikasi.\n"
            f"💵 <b>Klinika resepshnida to‘lanadigan qoldiq:</b> <b>60 000 so‘m</b>.\n"
            f"📋 <b>O‘zingiz bilan oling:</b> Barcha eski UTT va analiz qog‘ozlaringizni.\n\n"
            f"📌 <i>Belgilangan kunda klinikaga kelib, resepshnga ushbu xabarni va <b>№ {client_number}</b> raqamingizni ko‘rsating.</i>"
        )
        try:
            await bot.send_message(chat_id=app["user_id"], text=ticket_text)
        except Exception:
            pass

        approved_caption = (
            f"✅ <b>Tasdiqlandi | Mijoz raqami: № {client_number} | To‘lov: {_fmt_money(prepay)} so‘m</b>\n"
            f"👤 {app.get('patient_name', '')} | 📞 {app.get('phone_number', '')}\n"
            f"🗓 {when_str}"
        )
        for m in admin_msgs:
            try:
                await bot.edit_message_caption(
                    chat_id=m["chat_id"],
                    message_id=m["message_id"],
                    caption=approved_caption,
                    reply_markup=None
                )
            except Exception:
                pass

        await _update_all_admin_appointment_msgs(
            bot=bot,
            app_id=app_id,
            status_line=f"🟢 Tasdiqlandi | Mijoz raqami: № {client_number} | To‘lov: {_fmt_money(prepay)} so‘m",
            reply_markup=None
        )

        # Google Sheets'ga tasdiqlangan client_number bilan uzatish
        asyncio.create_task(google_sheets.append_lead_to_google_sheet({
            "id": app_id,
            "client_number": client_number,
            "date": datetime.now(UZ_TZ).strftime("%d.%m.%Y %H:%M"),
            "patient_name": app.get("patient_name", ""),
            "phone_number": app.get("phone_number", ""),
            "service": app.get("service", ""),
            "appointment_time": when_str,
            "status": f"To‘landi (№ {client_number})",
            "user_id": app.get("user_id", 0)
        }))

        await callback.answer(f"Tasdiqlandi! Mijoz raqami: № {client_number}")


@router.callback_query(F.data.startswith("adm_app:"))
async def process_admin_appointment_action(callback: CallbackQuery, bot: Bot):
    """Eski arizalar tugmalari uchun moslik"""
    user_id = callback.from_user.id if callback.from_user else 0
    perms = await database.get_admin_permissions(user_id)
    if not perms or not perms.get("can_manage_appointments"):
        return
    await callback.answer("Ushbu ariza eski formatda.", show_alert=False)


# ==========================================
# 8. ADMIN PANEL VA BUYRUQLAR
# ==========================================
@router.message(Command("admin"), StateFilter("*"))
async def cmd_admin_panel(message: Message, state: FSMContext):
    """Admin panelni ochish (Super Adminlar va dinamik adminlar uchun ruxsatlariga mos)"""
    user_id = message.from_user.id if message.from_user else 0
    perms = await database.get_admin_permissions(user_id)
    if not perms:
        return

    await state.clear()
    role_badge = "👑 Super Admin" if perms.get("is_super") else "🛡 Admin"
    text = (
        f"🔐 <b>«{CLINIC_NAME}» Boshqaruv Paneli</b> ({role_badge})\n\n"
        f"Xush kelibsiz! Sizga biriktirilgan bo‘limlar quyida ko‘rsatilgan:"
    )
    await message.answer(text=text, reply_markup=get_admin_panel_kb(perms))


@router.callback_query(F.data == "admin_stats")
async def admin_stats_callback(callback: CallbackQuery):
    """Statistika va Voronka (Drop-off) analitikasini ko'rsatish"""
    user_id = callback.from_user.id if callback.from_user else 0
    perms = await database.get_admin_permissions(user_id)
    if not perms or not perms.get("can_view_stats"):
        return

    stats = await database.get_appointments_stats()
    analytics = await database.get_funnel_analytics()
    menu = analytics["menu_stats"]
    funnel = analytics["funnel_stats"]
    dropoff = analytics["biggest_dropoff"]

    step_labels = {
        "step_1_disease": "1️⃣ Muammo tanlash",
        "step_2_name": "2️⃣ Ism kiritish",
        "step_3_phone": "3️⃣ Telefon kiritish",
        "step_4_date": "4️⃣ Sana tanlash",
        "step_5_time": "5️⃣ Vaqt tanlash",
        "step_6_confirmed": "6️⃣ Tasdiqlangan (Ariza)"
    }

    s1 = funnel["step_1_disease"]

    def pct(val: int) -> str:
        if s1 <= 0:
            return "0%"
        return f"{round((val / s1) * 100, 1)}%"

    funnel_lines = []
    for key, label in step_labels.items():
        val = funnel[key]
        funnel_lines.append(f"• {label}: <b>{val}</b> kishi ({pct(val)})")

    if dropoff:
        from_lbl = step_labels.get(dropoff["from_step"], dropoff["from_step"])
        to_lbl = step_labels.get(dropoff["to_step"], dropoff["to_step"])
        dropoff_text = (
            f"🚨 <b>Eng ko‘p to‘xtab qolish (Drop-off):</b>\n"
            f"<i>{from_lbl}</i> ➔ <i>{to_lbl}</i> bosqichida "
            f"<b>{dropoff['dropped_count']}</b> kishi (<b>{dropoff['dropped_pct']}%</b>) chiqib ketgan."
        )
    else:
        dropoff_text = "🚨 <b>Eng ko‘p to‘xtab qolish (Drop-off):</b> <i>Hozircha yetarli ma'lumot yo‘q</i>"

    text = (
        f"📊 <b>Klinika Bot Statistikasi va Voronka Tahlili:</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"👥 <b>Jami foydalanuvchilar:</b> {stats['total_users']} nafar\n"
        f"📅 <b>Bugungi arizalar:</b> {stats['today_appointments']} ta\n"
        f"⏳ <b>Kutilayotgan arizalar:</b> {stats['pending_appointments']} ta\n"
        f"📈 <b>Jami arizalar:</b> {stats['total_appointments']} ta\n\n"
        f"🔘 <b>Bo‘limlar bosilishi (jami / noyob):</b>\n"
        f"• 🚀 /start: <b>{menu['start']['total']}</b> ({menu['start']['unique']} kishi)\n"
        f"• 💰 Qabul narxi: <b>{menu['menu_price']['total']}</b> ({menu['menu_price']['unique']} kishi)\n"
        f"• 📅 Qabulga yozilish: <b>{menu['menu_booking']['total']}</b> ({menu['menu_booking']['unique']} kishi)\n"
        f"• 🩺 Xizmatlarimiz: <b>{menu['menu_services']['total']}</b> ({menu['menu_services']['unique']} kishi)\n"
        f"• 👩‍⚕️ Shifokor haqida: <b>{menu['menu_doctor']['total']}</b> ({menu['menu_doctor']['unique']} kishi)\n"
        f"• 📍 Manzil va ish vaqti: <b>{menu['menu_location']['total']}</b> ({menu['menu_location']['unique']} kishi)\n\n"
        f"📉 <b>Qabulga yozilish voronkasi (noyob foydalanuvchilar):</b>\n"
        + "\n".join(funnel_lines) + "\n\n"
        f"{dropoff_text}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"⏰ <i>Yangilangan vaqt: {datetime.now().strftime('%d.%m.%Y %H:%M')}</i>"
    )
    try:
        await callback.message.edit_text(text=text, reply_markup=get_admin_panel_kb(perms))
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data == "admin_meta_ads")
async def admin_meta_ads_callback(callback: CallbackQuery):
    """Meta Ads (Instagram/Facebook Target) natijalarini Graph API orqali olish va ko'rsatish"""
    user_id = callback.from_user.id if callback.from_user else 0
    perms = await database.get_admin_permissions(user_id)
    if not perms or not perms.get("can_view_stats"):
        return

    await callback.answer()
    loading_msg = await callback.message.answer("⏳ Meta Ads kabinetidan ma’lumotlar yuklanmoqda...")

    try:
        stats = await database.get_appointments_stats()
        analytics = await database.get_funnel_analytics()
        total_appointments = stats.get("total_appointments", 0)
        total_starts = analytics.get("menu_stats", {}).get("start", {}).get("total", 0)

        report_text = await meta_ads.get_meta_ads_report(
            total_appointments=total_appointments,
            total_starts=total_starts
        )
        await loading_msg.edit_text(text=report_text, reply_markup=get_admin_panel_kb(perms))
    except meta_ads.MetaAuthError as e:
        await loading_msg.edit_text(
            f"❌ Meta API tokeni ulanmagan yoki muddati tugagan. Server/Render sozlamalarida META_ACCESS_TOKEN ni tekshiring.\n\n<i>Sabab: {str(e)[:200]}</i>",
            reply_markup=get_admin_panel_kb(perms)
        )
    except Exception as e:
        await loading_msg.edit_text(
            f"❌ Meta Ads ma'lumotlarini yuklashda xatolik yuz berdi: {str(e)[:250]}",
            reply_markup=get_admin_panel_kb(perms)
        )


@router.callback_query(F.data == "admin_reception_list")
async def admin_reception_list_callback(callback: CallbackQuery, bot: Bot):
    """Bugungi va ertangi kun uchun tasdiqlangan (paid) mijozlar resepshn ro'yxati"""
    user_id = callback.from_user.id if callback.from_user else 0
    perms = await database.get_admin_permissions(user_id)
    if not perms or not (perms.get("can_manage_appointments") or perms.get("can_view_stats")):
        return

    await callback.answer("Resepshn ro‘yxati tayyorlanmoqda...")
    now_uz = datetime.now(UZ_TZ)
    today_str = now_uz.strftime("%Y-%m-%d")
    tomorrow_str = (now_uz + timedelta(days=1)).strftime("%Y-%m-%d")
    await send_reception_list(
        bot=bot,
        target_chat_id=callback.message.chat.id,
        target_dates=[today_str, tomorrow_str],
        title_label=f"Bugun ({today_str}) va Ertaga ({tomorrow_str}) Resepshn ro‘yxati"
    )


@router.callback_query(F.data == "admin_google_sheets")
async def admin_google_sheets_callback(callback: CallbackQuery):
    """Google Sheets havolasini taqdim etish yoki sozlash yo'riqnomasini ko'rsatish"""
    user_id = callback.from_user.id if callback.from_user else 0
    perms = await database.get_admin_permissions(user_id)
    if not perms or not (perms.get("can_manage_appointments") or perms.get("can_view_stats")):
        return

    sheet_url = os.getenv("GOOGLE_SHEET_URL", GOOGLE_SHEET_URL)
    if sheet_url and sheet_url.startswith("http"):
        text = (
            f"📊 <b>«{CLINIC_NAME}» Bemorlar Bazasi (Google Sheets)</b>\n\n"
            f"Barcha yangi mijozlar va qabul arizalari avtomatik tarzda Google Sheets jadvalingizga qo‘shib borilmoqda.\n\n"
            f"Telefonda ochish uchun quyidagi havolani bosing:\n"
            f"🔗 <a href='{sheet_url}'>Google Sheets Jadvalini Ochish</a>"
        )
    else:
        text = (
            f"📊 <b>Google Sheets Bemorlar Bazasi</b>\n\n"
            f"Hozirda Google Sheets havolasi botga kiritilmagan.\n\n"
            f"Lidlar to‘g‘ridan-to‘g‘ri shaxsiy Google hisobingizdagi jadvalga tushishi uchun "
            f"jadval ochib, uning havolasini server sozlamalariga kiriting."
        )
    await callback.message.answer(text=text, disable_web_page_preview=True)
    await callback.answer()


@router.callback_query(F.data == "admin_export")
async def admin_export_callback(callback: CallbackQuery):
    """Bemorlar arizalar bazasini Excel fayl shaklida yuborish"""
    user_id = callback.from_user.id if callback.from_user else 0
    perms = await database.get_admin_permissions(user_id)
    if not perms or not (perms.get("can_manage_appointments") or perms.get("can_view_stats")):
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
    user_id = callback.from_user.id if callback.from_user else 0
    perms = await database.get_admin_permissions(user_id)
    if not perms:
        return
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.answer("Admin panel yopildi.")


@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    """Xabar yuborishni boshlash"""
    user_id = callback.from_user.id if callback.from_user else 0
    perms = await database.get_admin_permissions(user_id)
    if not perms or not perms.get("can_broadcast"):
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
    perms = await database.get_admin_permissions(user_id)
    if not perms or not perms.get("can_broadcast"):
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


# ==========================================
# 9. DINAMIK ADMINLAR BOSHQARUVI
# ==========================================
def _format_perms_summary(adm: dict) -> str:
    """Admin huquqlarini qisqa chiroyli matnga o'girish"""
    labels = []
    if adm.get("can_manage_appointments"):
        labels.append("Arizalar")
    if adm.get("can_view_stats"):
        labels.append("Statistika/Target")
    if adm.get("can_broadcast"):
        labels.append("Broadcast")
    if adm.get("can_manage_admins"):
        labels.append("Adminlar boshqaruvi")
    return ", ".join(labels) if labels else "Huquq berilmagan"


@router.callback_query(F.data == "adm_mgr:menu")
async def admin_manage_menu(callback: CallbackQuery, state: FSMContext):
    """Adminlar boshqaruvi bo'limi"""
    user_id = callback.from_user.id if callback.from_user else 0
    perms = await database.get_admin_permissions(user_id)
    if not perms or not (perms.get("is_super") or perms.get("can_manage_admins")):
        return

    await state.clear()
    text = (
        f"👥 <b>Adminlar boshqaruvi</b>\n\n"
        f"Bu bo‘lim orqali yangi admin qo‘shishingiz, ularga alohida huquqlar "
        f"(ariza ko‘rish, savollarga javob berish, statistika, broadcast) belgilashingiz "
        f"yoki oddiy adminlarni tizimdan chiqarishingiz mumkin.\n\n"
        f"<i>Eslatma: Asosiy Super Adminlarni o‘chirib bo‘lmaydi.</i>"
    )
    try:
        await callback.message.edit_text(text=text, reply_markup=get_admin_manage_kb())
    except Exception:
        await callback.message.answer(text=text, reply_markup=get_admin_manage_kb())
    await callback.answer()


@router.callback_query(F.data == "adm_mgr:back")
async def admin_manage_back(callback: CallbackQuery, state: FSMContext):
    """Asosiy admin panelga qaytish"""
    user_id = callback.from_user.id if callback.from_user else 0
    perms = await database.get_admin_permissions(user_id)
    if not perms:
        return

    await state.clear()
    role_badge = "👑 Super Admin" if perms.get("is_super") else "🛡 Admin"
    text = (
        f"🔐 <b>«{CLINIC_NAME}» Boshqaruv Paneli</b> ({role_badge})\n\n"
        f"Xush kelibsiz! Sizga biriktirilgan bo‘limlar quyida ko‘rsatilgan:"
    )
    try:
        await callback.message.edit_text(text=text, reply_markup=get_admin_panel_kb(perms))
    except Exception:
        await callback.message.answer(text=text, reply_markup=get_admin_panel_kb(perms))
    await callback.answer()


@router.callback_query(F.data == "adm_mgr:add")
async def admin_manage_add_start(callback: CallbackQuery, state: FSMContext):
    """Yangi admin qo'shishni boshlash"""
    user_id = callback.from_user.id if callback.from_user else 0
    perms = await database.get_admin_permissions(user_id)
    if not perms or not (perms.get("is_super") or perms.get("can_manage_admins")):
        return

    await state.set_state(AdminManageState.waiting_for_admin_user)
    await callback.answer()
    await callback.message.answer(
        "➕ <b>Yangi admin qo‘shish:</b>\n\n"
        "Admin qilmoqchi bo‘lgan foydalanuvchining <b>Telegram ID</b> raqamini yuboring "
        "yoki uning biror xabarini shu yerga <b>forward (uzatish)</b> qiling:\n\n"
        "<i>(Eslatma: Yangi admin botga kamida bir marta /start bosgan bo‘lishi kerak)</i>",
        reply_markup=get_cancel_reply_kb()
    )


@router.message(AdminManageState.waiting_for_admin_user)
async def admin_manage_receive_user(message: Message, state: FSMContext):
    """Yangi admin ID sini (yoki forward xabarni) qabul qilish va huquqlarni tanlash"""
    user_id = message.from_user.id if message.from_user else 0
    perms = await database.get_admin_permissions(user_id)
    if not perms or not (perms.get("is_super") or perms.get("can_manage_admins")):
        await state.clear()
        return

    if message.text and is_menu_navigation(message.text) and "Bekor qilish" in message.text:
        await state.clear()
        await message.answer("Admin qo‘shish bekor qilindi.", reply_markup=get_main_menu_kb())
        return

    target_id = None
    target_name = None

    if message.forward_from:
        target_id = message.forward_from.id
        target_name = message.forward_from.full_name
    elif message.text and message.text.strip().isdigit():
        target_id = int(message.text.strip())
        target_name = f"Admin {target_id}"
    else:
        await message.answer(
            "❌ Iltimos, faqat raqamlardan iborat Telegram ID yuboring yoki "
            "foydalanuvchining xabarini shu yerga forward qiling:",
            reply_markup=get_cancel_reply_kb()
        )
        return

    if target_id in ADMIN_IDS:
        await state.clear()
        await message.answer(
            f"👑 <code>{target_id}</code> allaqachon tizimning asosiy <b>Super Admini</b> hisoblanadi!",
            reply_markup=get_main_menu_kb()
        )
        return

    default_perms = {
        "can_manage_appointments": True,
        "can_view_stats": False,
        "can_broadcast": False,
        "can_manage_admins": False,
    }
    await state.set_state(AdminManageState.selecting_permissions)
    await state.update_data(
        new_admin_id=target_id,
        new_admin_name=target_name,
        new_admin_perms=default_perms
    )

    await message.answer("Huquqlarni belgilang:", reply_markup=get_main_menu_kb())
    await message.answer(
        f"🛡 <b>Yangi admin:</b> {target_name} (<code>{target_id}</code>)\n\n"
        f"Quyidagi tugmalar orqali unga beriladigan huquqlarni belgilang va «💾 Saqlash» tugmasini bosing:",
        reply_markup=get_admin_perm_toggle_kb(default_perms)
    )


@router.callback_query(F.data.startswith("adm_perm:"), AdminManageState.selecting_permissions)
async def admin_manage_toggle_perm(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Yangi admin huquqlarini yoqish/o'chirish va saqlash"""
    user_id = callback.from_user.id if callback.from_user else 0
    perms = await database.get_admin_permissions(user_id)
    if not perms or not (perms.get("is_super") or perms.get("can_manage_admins")):
        return

    action = callback.data.split(":", 1)[1]
    data = await state.get_data()
    new_admin_id = data.get("new_admin_id")
    new_admin_name = data.get("new_admin_name", f"Admin {new_admin_id}")
    new_perms = data.get("new_admin_perms", {})

    if action == "cancel":
        await state.clear()
        await callback.message.edit_text("❌ Yangi admin qo‘shish bekor qilindi.", reply_markup=get_admin_manage_kb())
        await callback.answer()
        return

    if action == "save":
        await database.upsert_admin(
            user_id=new_admin_id,
            full_name=new_admin_name,
            added_by=user_id,
            perms=new_perms
        )
        await state.clear()

        # Yangi admin menyusida /admin buyrug'i ko'rinishi uchun scope o'rnatamiz
        try:
            await bot.set_my_commands(
                [
                    BotCommand(command="start", description="Botni qayta ishga tushirish va asosiy menyu"),
                    BotCommand(command="admin", description="Klinika boshqaruv paneli (faqat ma'murlar uchun)")
                ],
                scope=BotCommandScopeChat(chat_id=new_admin_id)
            )
        except Exception:
            pass

        summary = _format_perms_summary(new_perms)
        await callback.message.edit_text(
            f"✅ <b>Admin muvaffaqiyatli qo‘shildi!</b>\n\n"
            f"👤 <b>Admin:</b> {new_admin_name} (<code>{new_admin_id}</code>)\n"
            f"🔑 <b>Huquqlari:</b> {summary}",
            reply_markup=get_admin_manage_kb()
        )
        await callback.answer("Admin saqlandi!")
        return

    # Toggle permission flag
    if action in new_perms:
        new_perms[action] = not bool(new_perms[action])
        await state.update_data(new_admin_perms=new_perms)
        try:
            await callback.message.edit_reply_markup(reply_markup=get_admin_perm_toggle_kb(new_perms))
        except Exception:
            pass
    await callback.answer()


@router.callback_query(F.data == "adm_mgr:list")
async def admin_manage_list(callback: CallbackQuery):
    """Barcha adminlar ro'yxatini ko'rsatish"""
    user_id = callback.from_user.id if callback.from_user else 0
    perms = await database.get_admin_permissions(user_id)
    if not perms or not (perms.get("is_super") or perms.get("can_manage_admins")):
        return

    admins_list = await database.get_all_admins()

    lines = ["👑 <b>Asosiy Super Adminlar (o‘chirilmaydi):</b>"]
    for sid in ADMIN_IDS:
        lines.append(f"• <code>{sid}</code> — <i>Barcha huquqlar</i>")

    lines.append("\n🛡 <b>Qo‘shilgan adminlar:</b>")
    non_super = [a for a in admins_list if a["user_id"] not in ADMIN_IDS]
    if not non_super:
        lines.append("<i>Hozircha qo‘shimcha adminlar yo‘q.</i>")
    else:
        for adm in non_super:
            lines.append(
                f"• <b>{adm.get('full_name') or 'Admin'}</b> (<code>{adm['user_id']}</code>)\n"
                f"  🔑 {_format_perms_summary(adm)}"
            )

    text = "\n".join(lines)
    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=get_admin_list_kb(non_super, ADMIN_IDS)
        )
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data.startswith("adm_del:"))
async def admin_manage_delete(callback: CallbackQuery, bot: Bot):
    """Qo'shilgan adminni o'chirish (Super Adminlarni o'chirish taqiqlangan)"""
    user_id = callback.from_user.id if callback.from_user else 0
    perms = await database.get_admin_permissions(user_id)
    if not perms or not (perms.get("is_super") or perms.get("can_manage_admins")):
        return

    target_id = int(callback.data.split(":", 1)[1])
    if target_id in ADMIN_IDS:
        await callback.answer("Super Adminni o‘chirish mumkin emas!", show_alert=True)
        return

    deleted = await database.delete_admin(target_id)
    if deleted:
        try:
            await bot.set_my_commands(
                [BotCommand(command="start", description="Botni qayta ishga tushirish va asosiy menyu")],
                scope=BotCommandScopeChat(chat_id=target_id)
            )
        except Exception:
            pass
        await callback.answer("Admin o‘chirildi!", show_alert=False)
    else:
        await callback.answer("Admin topilmadi.", show_alert=False)

    # Ro'yxatni yangilash
    await admin_manage_list(callback)


# ==========================================
# 10. SUPER ADMIN: BAZANI TOZALASH VA TESTLARNI O'CHIRISH
# ==========================================
@router.callback_query(F.data == "db_clean:menu")
async def db_clean_menu_callback(callback: CallbackQuery):
    """Bazani tozalash bo'limi (faqat Super Admin uchun)"""
    user_id = callback.from_user.id if callback.from_user else 0
    perms = await database.get_admin_permissions(user_id)
    if not perms or not perms.get("is_super"):
        return

    recent = await database.get_recent_appointments(limit=20)
    text = (
        f"🗑 <b>Bazani tozalash (Super Admin)</b>\n\n"
        f"Bu yerdan to‘lanmagan barcha test yozuvlarni tozalashingiz yoki oxirgi 20 ta arizadan "
        f"keraksizini bittalab o‘chirishingiz mumkin.\n\n"
        f"<i>Eslatma: O‘chirilgan raqamlar (100+) bo‘sh o‘rin sifatida keyingi haqiqiy mijozlarga beriladi.</i>"
    )
    try:
        await callback.message.edit_text(text=text, reply_markup=get_db_clean_menu_kb(recent))
    except Exception:
        await callback.message.answer(text=text, reply_markup=get_db_clean_menu_kb(recent))
    await callback.answer()


@router.callback_query(F.data == "db_clean:ask_unpaid")
async def db_clean_ask_unpaid(callback: CallbackQuery):
    """To'lanmagan test yozuvlarni o'chirishni tasdiqlash"""
    user_id = callback.from_user.id if callback.from_user else 0
    perms = await database.get_admin_permissions(user_id)
    if not perms or not perms.get("is_super"):
        return

    await callback.message.edit_text(
        "⚠️ <b>Haqiqatan ham to‘lanmagan barcha test arizalarni o‘chirmoqchimisiz?</b>\n\n"
        "<i>(To‘lov qilgan `paid` mijozlar o‘chirilmaydi, ular xavfsiz saqlanadi.)</i>",
        reply_markup=get_db_clean_confirm_kb("db_clean:do_unpaid")
    )
    await callback.answer()


@router.callback_query(F.data == "db_clean:do_unpaid")
async def db_clean_do_unpaid(callback: CallbackQuery):
    """To'lanmagan test yozuvlarni o'chirish"""
    user_id = callback.from_user.id if callback.from_user else 0
    perms = await database.get_admin_permissions(user_id)
    if not perms or not perms.get("is_super"):
        return

    deleted_count = await database.delete_unpaid_test_appointments()
    await callback.answer(f"🧹 {deleted_count} ta test yozuv o‘chirildi!", show_alert=True)
    await db_clean_menu_callback(callback)


@router.callback_query(F.data.startswith("db_clean:ask_one:"))
async def db_clean_ask_one(callback: CallbackQuery):
    """Bitta arizani o'chirishni tasdiqlash"""
    user_id = callback.from_user.id if callback.from_user else 0
    perms = await database.get_admin_permissions(user_id)
    if not perms or not perms.get("is_super"):
        return

    app_id = int(callback.data.split(":")[2])
    app = await database.get_appointment_by_id(app_id)
    name = app.get("patient_name") if app else f"#{app_id}"
    await callback.message.edit_text(
        f"⚠️ <b>#{app_id} ({name})</b> arizasini bazadan butunlay o‘chirmoqchimisiz?",
        reply_markup=get_db_clean_confirm_kb(f"db_clean:do_one:{app_id}")
    )
    await callback.answer()


@router.callback_query(F.data.startswith("db_clean:do_one:"))
async def db_clean_do_one(callback: CallbackQuery):
    """Bitta arizani o'chirish"""
    user_id = callback.from_user.id if callback.from_user else 0
    perms = await database.get_admin_permissions(user_id)
    if not perms or not perms.get("is_super"):
        return

    app_id = int(callback.data.split(":")[2])
    ok = await database.delete_appointment_by_id(app_id)
    if ok:
        await callback.answer(f"🗑 #{app_id} o‘chirildi!", show_alert=False)
    else:
        await callback.answer("Ariza topilmadi.", show_alert=False)
    await db_clean_menu_callback(callback)
