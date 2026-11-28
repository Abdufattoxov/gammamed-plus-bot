import calendar
from datetime import datetime, date, timedelta
import os
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from config import GOOGLE_SHEET_URL

# O'zbekcha oylar
UZ_MONTHS = [
    "", "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
    "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr"
]

UZ_WEEKDAYS = ["Du", "Se", "Ch", "Pa", "Ju", "Sh", "Ya"]


# ==========================================
# 1. ASOSIY MENYU (ReplyKeyboardMarkup)
# ==========================================
def get_main_menu_kb() -> ReplyKeyboardMarkup:
    """Asosiy menyu tugmalari"""
    buttons = [
        [
            KeyboardButton(text="📅 Qabulga yozilish"),
            KeyboardButton(text="💰 Qabul narxi")
        ],
        [
            KeyboardButton(text="🩺 Xizmatlarimiz"),
            KeyboardButton(text="👩‍⚕️ Shifokor haqida")
        ],
        [
            KeyboardButton(text="📍 Manzil va ish vaqti")
        ]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


# ==========================================
# 2. NAVIGATSIYA UCHUN REPLY TUGMALAR
# ==========================================
def get_back_cancel_reply_kb() -> ReplyKeyboardMarkup:
    """Orqaga va bekor qilish reply tugmalari"""
    buttons = [
        [
            KeyboardButton(text="⬅️ Orqaga"),
            KeyboardButton(text="❌ Bekor qilish")
        ]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_phone_request_kb() -> ReplyKeyboardMarkup:
    """Telefon raqam kiritish bosqichi reply tugmalari"""
    buttons = [
        [
            KeyboardButton(text="⬅️ Orqaga"),
            KeyboardButton(text="❌ Bekor qilish")
        ]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


def get_cancel_reply_kb() -> ReplyKeyboardMarkup:
    """Faqat bekor qilish reply tugmasi"""
    buttons = [
        [KeyboardButton(text="❌ Bekor qilish")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)


# ==========================================
# 3. QABULGA YOZILISH (1-BOSQICH) INLINE TUGMALARI
# ==========================================
def get_problems_inline_kb() -> InlineKeyboardMarkup:
    """1-bosqich: Bemor shikoyati / muammosini tanlash inline klaviaturasi"""
    buttons = [
        [
            InlineKeyboardButton(
                text="👶 1. Bepushtlik (homila bo‘lmasligi)",
                callback_data="prob:bepushtlik"
            )
        ],
        [
            InlineKeyboardButton(
                text="😣 2. Hayz og‘riqlari va sikl buzilishi",
                callback_data="prob:hayz_ogriq"
            )
        ],
        [
            InlineKeyboardButton(
                text="🌸 3. Endometrioz va adenomioz",
                callback_data="prob:endometrioz"
            )
        ],
        [
            InlineKeyboardButton(
                text="🔄 4. Tuxumdonlar polikistozi (SPKY)",
                callback_data="prob:polikistoz"
            )
        ],
        [
            InlineKeyboardButton(
                text="🔬 5. Bachadon miomasi",
                callback_data="prob:mioma"
            )
        ],
        [
            InlineKeyboardButton(
                text="💧 6. Tuxumdon kistalari",
                callback_data="prob:kista"
            )
        ],
        [
            InlineKeyboardButton(
                text="🩺 7. Bachadon bo‘yni eroziyasi",
                callback_data="prob:eroziya"
            )
        ],
        [
            InlineKeyboardButton(
                text="❄️ 8. Shamollash va adneksit",
                callback_data="prob:adneksit"
            )
        ],
        [
            InlineKeyboardButton(
                text="🌿 9. Molochnitsa va ajralmalar",
                callback_data="prob:molochnitsa"
            )
        ],
        [
            InlineKeyboardButton(
                text="☀️ 10. Klimaks va gormonal o‘zgarishlar",
                callback_data="prob:klimaks"
            )
        ],
        [
            InlineKeyboardButton(
                text="📋 Va boshqa ginekologik kasalliklar",
                callback_data="prob:boshqa_muammo"
            )
        ],
        [
            InlineKeyboardButton(
                text="❌ Bekor qilish",
                callback_data="action_cancel"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ==========================================
# 4. INTERAKTIV QABUL KALENDARI (4-BOSQICH)
# ==========================================
def generate_calendar_kb(year: int, month: int) -> InlineKeyboardMarkup:
    """
    Qabul kunini tanlash uchun interaktiv oylik kalendar.
    O'tgan kunlar va Yakshanba (dam olish kuni) belgilanmaydi.
    """
    now = datetime.now()
    today = now.date()

    keyboard: list[list[InlineKeyboardButton]] = []

    # 1. Tezkor tanlov tugmalari (Bugun, Ertaga - agar yakshanba bo'lmasa)
    quick_row: list[InlineKeyboardButton] = []
    
    # Bugun
    if today.weekday() != 6: # Yakshanba emas
        quick_row.append(
            InlineKeyboardButton(
                text=f"⚡️ Bugun ({today.day}-{UZ_MONTHS[today.month][:3]})",
                callback_data=f"cal_date:{today.strftime('%Y-%m-%d')}"
            )
        )
    # Ertaga
    tomorrow = today + timedelta(days=1)
    if tomorrow.weekday() != 6:
        quick_row.append(
            InlineKeyboardButton(
                text=f"⚡️ Ertaga ({tomorrow.day}-{UZ_MONTHS[tomorrow.month][:3]})",
                callback_data=f"cal_date:{tomorrow.strftime('%Y-%m-%d')}"
            )
        )
    if quick_row:
        keyboard.append(quick_row)

    # 2. Kalendar sarlavhasi (Oy va Yil)
    month_name = UZ_MONTHS[month]
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1

    header_row = [
        InlineKeyboardButton(text="◀️", callback_data=f"cal_nav:{prev_year}:{prev_month}"),
        InlineKeyboardButton(text=f"🗓 {month_name} {year}", callback_data="cal_ignore:title"),
        InlineKeyboardButton(text="▶️", callback_data=f"cal_nav:{next_year}:{next_month}")
    ]
    keyboard.append(header_row)

    # 3. Hafta kunlari qatori
    weekdays_row = [
        InlineKeyboardButton(text=day, callback_data="cal_ignore:weekday")
        for day in UZ_WEEKDAYS
    ]
    keyboard.append(weekdays_row)

    # 4. Kunlar matritsasi
    cal = calendar.monthcalendar(year, month)
    for week in cal:
        row: list[InlineKeyboardButton] = []
        for day_num in week:
            if day_num == 0:
                row.append(InlineKeyboardButton(text=" ", callback_data="cal_ignore:empty"))
            else:
                current_date = date(year, month, day_num)
                # Yakshanba (weekday == 6)
                if current_date.weekday() == 6:
                    row.append(InlineKeyboardButton(text=f"⛔️{day_num}", callback_data="cal_ignore:sunday"))
                elif current_date < today:
                    row.append(InlineKeyboardButton(text=f"·{day_num}·", callback_data="cal_ignore:past"))
                else:
                    # Tanlash mumkin bo'lgan sana
                    date_str = current_date.strftime("%Y-%m-%d")
                    row.append(InlineKeyboardButton(text=str(day_num), callback_data=f"cal_date:{date_str}"))
        keyboard.append(row)

    # 5. Bekor qilish tugmasi
    keyboard.append([
        InlineKeyboardButton(text="❌ Bekor qilish", callback_data="action_cancel")
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_time_slots_inline_kb(date_str: str) -> InlineKeyboardMarkup:
    """Tanlangan sana uchun aniq qabul vaqti oraliqlari (09:00 - 17:00)"""
    buttons = [
        [
            InlineKeyboardButton(text="🌅 09:00 — 11:00", callback_data=f"slot:{date_str}:09:00-11:00"),
            InlineKeyboardButton(text="☀️ 11:00 — 13:00", callback_data=f"slot:{date_str}:11:00-13:00")
        ],
        [
            InlineKeyboardButton(text="🌤 13:00 — 15:00", callback_data=f"slot:{date_str}:13:00-15:00"),
            InlineKeyboardButton(text="🌆 15:00 — 17:00", callback_data=f"slot:{date_str}:15:00-17:00")
        ],
        [
            InlineKeyboardButton(text="🔄 Boshqa sanani tanlash", callback_data="cal_reopen"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data="action_cancel")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ==========================================
# 5. ADMIN BILDIRISHNOMASI VA PANEL TUGMALARI
# ==========================================
def get_admin_appointment_kb(appointment_id: int, current_status: str = "Kutilmoqda") -> InlineKeyboardMarkup:
    """Adminlarga kelgan ariza ostidagi tugmalar (holatga qarab dinamik belgilanadi)"""
    is_accepted = "Qabul qilindi" in current_status
    is_called = "Qo'ng'iroq qilindi" in current_status

    accepted_label = "✅ Qabul qilingan" if is_accepted else "✅ Qabul qilish"
    called_label = "📞 Qo‘ng‘iroq qilingan" if is_called else "📞 Qo‘ng‘iroq qilish"

    buttons = [
        [
            InlineKeyboardButton(
                text=accepted_label,
                callback_data=f"adm_app:{appointment_id}:accepted"
            ),
            InlineKeyboardButton(
                text=called_label,
                callback_data=f"adm_app:{appointment_id}:called"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_admin_panel_kb(perms: dict | None = None) -> InlineKeyboardMarkup:
    """Admin panel boshqaruv tugmalari (har bir admin uchun faqat ruxsat etilgan tugmalar)"""
    if perms is None:
        perms = {
            "is_super": True,
            "can_manage_appointments": True,
            "can_reply_questions": True,
            "can_view_stats": True,
            "can_broadcast": True,
            "can_manage_admins": True,
        }

    sheet_url = os.getenv("GOOGLE_SHEET_URL", GOOGLE_SHEET_URL)
    if sheet_url and sheet_url.startswith("http"):
        sheet_button = InlineKeyboardButton(
            text="📊 Baza (Google Sheets)",
            url=sheet_url
        )
    else:
        sheet_button = InlineKeyboardButton(
            text="📊 Baza (Google Sheets)",
            callback_data="admin_google_sheets"
        )

    buttons = []

    row1 = []
    if perms.get("can_view_stats"):
        row1.append(InlineKeyboardButton(text="📊 Statistika / Voronka", callback_data="admin_stats"))
    if perms.get("can_manage_appointments") or perms.get("can_view_stats"):
        row1.append(sheet_button)
    if row1:
        buttons.append(row1)

    if perms.get("can_view_stats"):
        buttons.append([
            InlineKeyboardButton(text="📈 Target natijalari", callback_data="admin_meta_ads")
        ])

    if perms.get("can_broadcast"):
        buttons.append([
            InlineKeyboardButton(text="📢 Barchaga xabar yuborish (Broadcast)", callback_data="admin_broadcast")
        ])

    if perms.get("is_super") or perms.get("can_manage_admins"):
        buttons.append([
            InlineKeyboardButton(text="👥 Adminlar boshqaruvi", callback_data="adm_mgr:menu")
        ])

    buttons.append([
        InlineKeyboardButton(text="❌ Yopish", callback_data="admin_close")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_admin_manage_kb() -> InlineKeyboardMarkup:
    """Adminlar boshqaruvi menyusi"""
    buttons = [
        [
            InlineKeyboardButton(text="➕ Admin qo‘shish", callback_data="adm_mgr:add"),
            InlineKeyboardButton(text="📋 Adminlar ro‘yxati", callback_data="adm_mgr:list")
        ],
        [
            InlineKeyboardButton(text="⬅️ Admin panelga qaytish", callback_data="adm_mgr:back")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_admin_perm_toggle_kb(perms: dict) -> InlineKeyboardMarkup:
    """Yangi admin huquqlarini belgilash tugmalari"""
    def icon(key: str) -> str:
        return "✅" if perms.get(key) else "❌"

    buttons = [
        [
            InlineKeyboardButton(
                text=f"{icon('can_manage_appointments')} Arizalar",
                callback_data="adm_perm:can_manage_appointments"
            ),
            InlineKeyboardButton(
                text=f"{icon('can_view_stats')} Statistika/Target",
                callback_data="adm_perm:can_view_stats"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{icon('can_broadcast')} Xabar tarqatish",
                callback_data="adm_perm:can_broadcast"
            ),
            InlineKeyboardButton(
                text=f"{icon('can_manage_admins')} Adminlar boshqaruvi",
                callback_data="adm_perm:can_manage_admins"
            )
        ],
        [
            InlineKeyboardButton(text="💾 Saqlash", callback_data="adm_perm:save"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data="adm_perm:cancel")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_admin_list_kb(admins_list: list[dict], super_admin_ids: list[int]) -> InlineKeyboardMarkup:
    """Qo'shilgan adminlarni o'chirish tugmalari (Super Adminlar uchun o'chirish tugmasi chiqmaydi)"""
    buttons = []
    for adm in admins_list:
        uid = adm["user_id"]
        if uid in super_admin_ids:
            continue
        name = adm.get("full_name") or str(uid)
        buttons.append([
            InlineKeyboardButton(
                text=f"🗑 O‘chirish: {name} ({uid})",
                callback_data=f"adm_del:{uid}"
            )
        ])
    buttons.append([
        InlineKeyboardButton(text="⬅️ Orqaga", callback_data="adm_mgr:menu")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_services_info_inline_kb(button_text: str = "📅 Hozir qabulga yozilish") -> InlineKeyboardMarkup:
    """Xizmatlar, Narxlar yoki Shifokor haqida bo'limi ostidagi tezkor qabul tugmasi"""
    buttons = [
        [
            InlineKeyboardButton(
                text=button_text,
                callback_data="start_appointment_flow"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
