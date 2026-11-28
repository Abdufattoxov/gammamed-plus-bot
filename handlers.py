import os
import re
import asyncio
from datetime import datetime
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
    CONSULTATION_OFFER,
    SAFETY_NOTICE,
    GOOGLE_SHEET_URL
)
import database
import google_sheets
import meta_ads
from states import (
    AppointmentState,
    AnonymousQuestionState,
    QuestionReplyState,
    AdminBroadcastState,
    AdminManageState
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
    get_admin_panel_kb,
    get_admin_manage_kb,
    get_admin_perm_toggle_kb,
    get_admin_list_kb,
    get_question_reply_kb,
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
        "Qabul narxi",
        "Xizmatlarimiz",
        "Xizmatlar va narxlar",
        "Shifokor haqida",
        "Manzil va ish vaqti",
        "Shifokorga savol",
        "Anonim savol",
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
        f"1️⃣ <b>Er-xotin birgalikdagi chuqur suhbat va ko‘rik</b> — bitta narxning o‘zida turmush o‘rtog‘ingiz bilan birga kirasiz;\n"
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
# 5. SHIFOKORGA SAVOL BERISH VA JAVOB QAYTARISH
# ==========================================
@router.message(F.text.func(lambda t: t and ("Shifokorga savol" in t or "Anonim savol" in t)), StateFilter("*"))
async def anon_question_start(message: Message, state: FSMContext):
    """Shifokorga savol berishni boshlash"""
    await state.clear()
    await track_event(message, "menu_anon_question")
    await state.set_state(AnonymousQuestionState.waiting_for_question)
    text = (
        f"💬 <b>Shifokorga savol yo‘llash</b>\n\n"
        f"Siz ayollar salomatligi yoki psixosomatika bo‘yicha o‘zingizni o‘ylantirayotgan "
        f"savolingizni bevosita <b>{DOCTOR_NAME}</b>ga yuborishingiz mumkin.\n\n"
        f"🔒 <b>Maxfiylik kafolati:</b>\n"
        f"Savolingiz begonalarga ko‘rinmaydi, faqat shifokor va ma’muriyatga yetib boradi. "
        f"Javob to‘g‘ridan-to‘g‘ri sizning shu botingizga yuboriladi.\n\n"
        f"{SAFETY_NOTICE}\n\n"
        f"✍️ <i>Savolingizni bitta xabarda batafsil yozib yuboring:</i>"
    )
    await message.answer(
        text=text,
        reply_markup=get_cancel_reply_kb()
    )


@router.message(AnonymousQuestionState.waiting_for_question, F.text)
async def anon_question_receive(message: Message, state: FSMContext, bot: Bot):
    """Savolni qabul qilish, bazaga saqlash va javob huquqiga ega adminlarga yuborish"""
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

    user = message.from_user
    user_id = user.id if user else 0
    username = user.username if user and user.username else ""
    full_name = user.full_name if user else "Noma'lum"

    question_id = await database.save_anonymous_question(
        user_id=user_id,
        question_text=question_text,
        username=username,
        full_name=full_name
    )
    await state.clear()

    reply_text = (
        f"🕊 <b>Savolingiz muvaffaqiyatli qabul qilindi!</b>\n\n"
        f"Savolingiz <b>#Q-{question_id}</b> raqami bilan shifokor va ma’muriyatga yetkazildi. "
        f"Javob tayyor bo‘lishi bilan shu bot orqali sizga yuboriladi.\n\n"
        f"Salomatligingizga befarq bo‘lmaganingiz uchun tashakkur!"
    )
    await message.answer(
        text=reply_text,
        reply_markup=get_main_menu_kb()
    )

    username_display = f"@{username}" if username else "mavjud emas"
    notify_text = (
        f"💬 <b>YANGI SAVOL (#Q-{question_id})</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Ismi:</b> <a href='tg://user?id={user_id}'>{full_name}</a>\n"
        f"🔗 <b>Username:</b> {username_display}\n"
        f"🆔 <b>Telegram ID:</b> <code>{user_id}</code>\n"
        f"⏰ <b>Vaqti:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📝 <b>Savol matni:</b>\n"
        f"<i>«{question_text}»</i>"
    )

    target_admins = await database.get_admins_with_permission("can_reply_questions")
    for admin_id in target_admins:
        try:
            sent_msg = await bot.send_message(
                chat_id=admin_id,
                text=notify_text,
                reply_markup=get_question_reply_kb(question_id)
            )
            await database.save_admin_question_message(question_id, sent_msg.chat.id, sent_msg.message_id)
        except Exception:
            pass

    if ADMIN_GROUP_ID:
        try:
            sent_msg = await bot.send_message(
                chat_id=ADMIN_GROUP_ID,
                text=notify_text,
                reply_markup=get_question_reply_kb(question_id)
            )
            await database.save_admin_question_message(question_id, sent_msg.chat.id, sent_msg.message_id)
        except Exception:
            pass


@router.callback_query(F.data.startswith("reply_q:"))
async def start_question_reply(callback: CallbackQuery, state: FSMContext):
    """Admin savolga javob yozish tugmasini bosganda"""
    user_id = callback.from_user.id if callback.from_user else 0
    perms = await database.get_admin_permissions(user_id)
    if not perms or not perms.get("can_reply_questions"):
        return

    q_id = int(callback.data.split(":", 1)[1])
    question = await database.get_question_by_id(q_id)
    if not question:
        await callback.answer("Savol bazadan topilmadi.", show_alert=True)
        return

    await state.set_state(QuestionReplyState.waiting_for_reply)
    await state.update_data(reply_question_id=q_id)
    await callback.answer()
    await callback.message.answer(
        f"✍️ <b>#Q-{q_id} raqamli savolga javob yozing:</b>\n\n"
        f"<i>Foydalanuvchi: {question.get('full_name') or 'Noma’lum'}</i>\n"
        f"Javob matnini yuboring (bekor qilish uchun «❌ Bekor qilish» tugmasini bosing):",
        reply_markup=get_cancel_reply_kb()
    )


@router.message(QuestionReplyState.waiting_for_reply, F.text)
async def send_question_reply(message: Message, state: FSMContext, bot: Bot):
    """Admin yozgan javobni to'g'ridan-to'g'ri savol egasiga yuborish va adminlarda xabarni yangilash"""
    user_id = message.from_user.id if message.from_user else 0
    perms = await database.get_admin_permissions(user_id)
    if not perms or not perms.get("can_reply_questions"):
        await state.clear()
        return

    if is_menu_navigation(message.text) and "Bekor qilish" in message.text:
        await state.clear()
        await message.answer("Javob yozish bekor qilindi.", reply_markup=get_main_menu_kb())
        return

    data = await state.get_data()
    q_id = data.get("reply_question_id")
    await state.clear()

    question = await database.get_question_by_id(q_id)
    if not question:
        await message.answer("❌ Savol bazadan topilmadi.", reply_markup=get_main_menu_kb())
        return

    reply_text = message.text.strip()
    admin_name = message.from_user.first_name if message.from_user else "Admin"

    # 1. Savol egasiga to'g'ridan-to'g'ri javob yuborish
    patient_msg = (
        f"👩‍⚕️ <b>Dr. Zarifa klinikasidan savolingizga javob:</b>\n\n"
        f"{reply_text}"
    )
    try:
        await bot.send_message(chat_id=question["user_id"], text=patient_msg)
        sent_ok = True
    except Exception:
        sent_ok = False

    # 2. Bazada answered qilib belgilash
    await database.update_question_answered(q_id, reply_text, admin_name)

    # 3. Barcha adminlardagi savol xabarini yangilash
    q_username = question.get("username") or ""
    q_uname_disp = f"@{q_username}" if q_username else "mavjud emas"
    q_full_name = question.get("full_name") or "Foydalanuvchi"
    q_uid = question.get("user_id")
    updated_admin_text = (
        f"💬 <b>SAVOL (#Q-{q_id})</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Ismi:</b> <a href='tg://user?id={q_uid}'>{q_full_name}</a>\n"
        f"🔗 <b>Username:</b> {q_uname_disp}\n"
        f"🆔 <b>Telegram ID:</b> <code>{q_uid}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📝 <b>Savol:</b> <i>«{question.get('question_text', '')}»</i>\n\n"
        f"✅ <b>Ushbu savolga javob berildi ({admin_name} tomonidan):</b>\n"
        f"<i>{reply_text}</i>"
    )

    admin_msgs = await database.get_admin_question_messages(q_id)
    for m in admin_msgs:
        try:
            await bot.edit_message_text(
                chat_id=m["chat_id"],
                message_id=m["message_id"],
                text=updated_admin_text,
                reply_markup=None
            )
        except Exception:
            pass

    if sent_ok:
        await message.answer(
            f"✅ #Q-{q_id} raqamli savolga javob foydalanuvchiga muvaffaqiyatli yuborildi!",
            reply_markup=get_main_menu_kb()
        )
    else:
        await message.answer(
            f"⚠️ Bazada belgilandi, lekin foydalanuvchi botni bloklaganligi sababli xabar yetib bormadi.",
            reply_markup=get_main_menu_kb()
        )


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
        appointment_time=full_appointment_time
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
# 7. ADMIN ARIZA STATUSINI O'ZGARTIRISH
# ==========================================
@router.callback_query(F.data.startswith("adm_app:"))
async def process_admin_appointment_action(callback: CallbackQuery, bot: Bot):
    """Admin ariza holatini o'zgartirishi — BARCHA adminlarda bir vaqtda sinxron yangilanadi"""
    user_id = callback.from_user.id if callback.from_user else 0
    perms = await database.get_admin_permissions(user_id)
    if not perms or not perms.get("can_manage_appointments"):
        return

    parts = callback.data.split(":")
    app_id = int(parts[1])
    action = parts[2]

    admin_name = callback.from_user.first_name if callback.from_user else "Admin"

    if action == "accepted":
        status_label = "Qabul qilindi"
        status_text = f"✅ Qabul qilindi ({admin_name} tomonidan)"
    elif action == "called":
        status_label = "Qo'ng'iroq qilindi"
        status_text = f"📞 Qo‘ng‘iroq qilindi ({admin_name} tomonidan)"
    else:
        status_label = "Noma'lum"
        status_text = "Noma'lum"

    # 1. Bazada arizaning joriy holatini yangilash
    await database.update_appointment_status(app_id, status_label)

    # 2. Xabar matnidagi holat qatorini yangilash
    current_html = callback.message.html_text or ""
    if "📌 <b>Holati:</b>" in current_html:
        updated_text = re.sub(r"📌 <b>Holati:</b>.*", f"📌 <b>Holati:</b> <b>{status_text}</b>", current_html, flags=re.DOTALL)
    elif "📌 Holati:" in current_html:
        updated_text = re.sub(r"📌 Holati:.*", f"📌 <b>Holati:</b> <b>{status_text}</b>", current_html, flags=re.DOTALL)
    else:
        updated_text = f"{current_html}\n\n📌 <b>Holati:</b> <b>{status_text}</b>"

    updated_kb = get_admin_appointment_kb(app_id, status_label)

    # 3. Ushbu arizaga tegishli barcha admin xabarlarini topamiz
    admin_messages = await database.get_admin_appointment_messages(app_id)

    # Agar joriy bosilgan xabar bazaga tushmagan bo'lsa, ro'yxatga kiritamiz
    current_chat_id = callback.message.chat.id
    current_msg_id = callback.message.message_id
    already_tracked = any(
        m.get("chat_id") == current_chat_id and m.get("message_id") == current_msg_id 
        for m in admin_messages
    )
    if not already_tracked:
        admin_messages.append({"chat_id": current_chat_id, "message_id": current_msg_id})
        await database.save_admin_appointment_message(app_id, current_chat_id, current_msg_id)

    # 4. BARCHA adminlarning xabarlarini bir vaqtning o'zida yangilash
    for m in admin_messages:
        try:
            await bot.edit_message_text(
                chat_id=m["chat_id"],
                message_id=m["message_id"],
                text=updated_text,
                reply_markup=updated_kb
            )
        except Exception:
            pass

    await callback.answer(f"Holat barcha adminlarda yangilandi: {status_text}")


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
        f"• 📍 Manzil va ish vaqti: <b>{menu['menu_location']['total']}</b> ({menu['menu_location']['unique']} kishi)\n"
        f"• 💬 Shifokorga savol: <b>{menu['menu_anon_question']['total']}</b> ({menu['menu_anon_question']['unique']} kishi)\n\n"
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
    if adm.get("can_reply_questions"):
        labels.append("Savollar")
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
        "can_reply_questions": True,
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
