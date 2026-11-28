import os
import aiosqlite
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from config import DATABASE_NAME, DATABASE_URL, ADMIN_IDS

_pg_pool = None


def is_postgres() -> bool:
    """PostgreSQL ulanganligini tekshirish"""
    return bool(DATABASE_URL and (DATABASE_URL.startswith("postgres://") or DATABASE_URL.startswith("postgresql://")))


def get_pg_url() -> str:
    """Render postgres:// URL formatini asyncpg talab qiladigan postgresql:// ga moslash"""
    url = DATABASE_URL
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    return url


async def get_pg_pool():
    """PostgreSQL ulanishlar havzasi (connection pool)"""
    global _pg_pool
    if _pg_pool is None:
        import asyncpg
        _pg_pool = await asyncpg.create_pool(get_pg_url(), min_size=1, max_size=10)
    return _pg_pool


async def init_db():
    """Ma'lumotlar bazasi va jadvallarni yaratish (PostgreSQL yoki SQLite)"""
    if is_postgres():
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    full_name TEXT,
                    username TEXT,
                    phone TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS appointments (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT,
                    service TEXT,
                    region TEXT,
                    patient_name TEXT,
                    phone_number TEXT,
                    notes TEXT,
                    status TEXT DEFAULT 'Kutilmoqda',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS questions (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT,
                    question_text TEXT,
                    status TEXT DEFAULT 'Yangi',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS appointment_admin_messages (
                    id SERIAL PRIMARY KEY,
                    appointment_id INTEGER,
                    chat_id BIGINT,
                    message_id BIGINT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS user_events (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT,
                    username TEXT,
                    full_name TEXT,
                    step_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS admins (
                    user_id BIGINT PRIMARY KEY,
                    full_name TEXT,
                    added_by BIGINT,
                    can_manage_appointments BOOLEAN DEFAULT FALSE,
                    can_reply_questions BOOLEAN DEFAULT FALSE,
                    can_view_stats BOOLEAN DEFAULT FALSE,
                    can_broadcast BOOLEAN DEFAULT FALSE,
                    can_manage_admins BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS question_admin_messages (
                    id SERIAL PRIMARY KEY,
                    question_id INTEGER,
                    chat_id BIGINT,
                    message_id BIGINT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            # Mavjud questions jadvalini eski ma'lumotlarga zarar yetkazmasdan kengaytirish
            for col_name in ("username", "full_name", "answer_text", "answered_by"):
                await conn.execute(f"ALTER TABLE questions ADD COLUMN IF NOT EXISTS {col_name} TEXT;")
    else:
        async with aiosqlite.connect(DATABASE_NAME) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    full_name TEXT,
                    username TEXT,
                    phone TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS appointments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    service TEXT,
                    region TEXT,
                    patient_name TEXT,
                    phone_number TEXT,
                    notes TEXT,
                    status TEXT DEFAULT 'Kutilmoqda',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    question_text TEXT,
                    status TEXT DEFAULT 'Yangi',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS appointment_admin_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    appointment_id INTEGER,
                    chat_id INTEGER,
                    message_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    username TEXT,
                    full_name TEXT,
                    step_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS admins (
                    user_id INTEGER PRIMARY KEY,
                    full_name TEXT,
                    added_by INTEGER,
                    can_manage_appointments INTEGER DEFAULT 0,
                    can_reply_questions INTEGER DEFAULT 0,
                    can_view_stats INTEGER DEFAULT 0,
                    can_broadcast INTEGER DEFAULT 0,
                    can_manage_admins INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS question_admin_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question_id INTEGER,
                    chat_id INTEGER,
                    message_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Mavjud questions jadvalini eski ma'lumotlarga zarar yetkazmasdan kengaytirish
            async with db.execute("PRAGMA table_info(questions)") as cursor:
                existing_cols = {row[1] for row in await cursor.fetchall()}
            for col_name in ("username", "full_name", "answer_text", "answered_by"):
                if col_name not in existing_cols:
                    await db.execute(f"ALTER TABLE questions ADD COLUMN {col_name} TEXT")
            await db.commit()


async def register_user(user_id: int, full_name: str, username: str | None, phone: str | None = None):
    """Foydalanuvchini ro'yxatdan o'tkazish yoki ma'lumotlarini yangilash"""
    if is_postgres():
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO users (user_id, full_name, username, phone)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT(user_id) DO UPDATE SET
                    full_name = EXCLUDED.full_name,
                    username = EXCLUDED.username,
                    phone = COALESCE(EXCLUDED.phone, users.phone);
            """, user_id, full_name, username, phone)
    else:
        async with aiosqlite.connect(DATABASE_NAME) as db:
            await db.execute("""
                INSERT INTO users (user_id, full_name, username, phone)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    full_name = excluded.full_name,
                    username = excluded.username,
                    phone = COALESCE(excluded.phone, users.phone)
            """, (user_id, full_name, username, phone))
            await db.commit()


async def get_total_users_count() -> int:
    """Jami bot foydalanuvchilari soni"""
    if is_postgres():
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            val = await conn.fetchval("SELECT COUNT(*) FROM users;")
            return val or 0
    else:
        async with aiosqlite.connect(DATABASE_NAME) as db:
            async with db.execute("SELECT COUNT(*) FROM users") as cursor:
                row = await cursor.fetchone()
                return row[0] if row else 0


async def get_all_user_ids() -> list[int]:
    """Barcha foydalanuvchilar ID larini olish (xabar tarqatish uchun)"""
    if is_postgres():
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT user_id FROM users;")
            return [int(r["user_id"]) for r in rows]
    else:
        async with aiosqlite.connect(DATABASE_NAME) as db:
            async with db.execute("SELECT user_id FROM users") as cursor:
                rows = await cursor.fetchall()
                return [row[0] for row in rows]


async def create_appointment(
    user_id: int,
    service: str,
    patient_name: str,
    phone_number: str,
    appointment_time: str = "Ko'rsatilmadi",
    region: str = "Bulung'ur",
    notes: str = ""
) -> int:
    """Yangi qabul arizasini bazaga kiritish"""
    full_notes = f"Qabul vaqti: {appointment_time}" if not notes else f"Qabul: {appointment_time} | {notes}"

    if is_postgres():
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            row_id = await conn.fetchval("""
                INSERT INTO appointments (user_id, service, region, patient_name, phone_number, notes, status)
                VALUES ($1, $2, $3, $4, $5, $6, 'Kutilmoqda')
                RETURNING id;
            """, user_id, service, region, patient_name, phone_number, full_notes)
            return row_id
    else:
        async with aiosqlite.connect(DATABASE_NAME) as db:
            cursor = await db.execute("""
                INSERT INTO appointments (user_id, service, region, patient_name, phone_number, notes, status)
                VALUES (?, ?, ?, ?, ?, ?, 'Kutilmoqda')
            """, (user_id, service, region, patient_name, phone_number, full_notes))
            await db.commit()
            return cursor.lastrowid


async def get_appointment_by_id(app_id: int) -> dict | None:
    """Arizani ID bo'yicha olish"""
    if is_postgres():
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM appointments WHERE id = $1;", app_id)
            return dict(row) if row else None
    else:
        async with aiosqlite.connect(DATABASE_NAME) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM appointments WHERE id = ?", (app_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None


async def update_appointment_status(app_id: int, status: str):
    """Ariza holatini yangilash (Qabul qilindi / Qo'ng'iroq qilindi / Bekor qilindi)"""
    if is_postgres():
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            await conn.execute("UPDATE appointments SET status = $1 WHERE id = $2;", status, app_id)
    else:
        async with aiosqlite.connect(DATABASE_NAME) as db:
            await db.execute("""
                UPDATE appointments
                SET status = ?
                WHERE id = ?
            """, (status, app_id))
            await db.commit()


async def save_admin_appointment_message(appointment_id: int, chat_id: int, message_id: int):
    """Adminlarga yuborilgan ariza xabarini saqlash (barcha adminlarda sinxron yangilash uchun)"""
    if is_postgres():
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO appointment_admin_messages (appointment_id, chat_id, message_id)
                VALUES ($1, $2, $3);
            """, appointment_id, chat_id, message_id)
    else:
        async with aiosqlite.connect(DATABASE_NAME) as db:
            await db.execute("""
                INSERT INTO appointment_admin_messages (appointment_id, chat_id, message_id)
                VALUES (?, ?, ?)
            """, (appointment_id, chat_id, message_id))
            await db.commit()


async def get_admin_appointment_messages(appointment_id: int) -> list[dict]:
    """Arizaga tegishli barcha admin xabarlari (chat_id va message_id) ni olish"""
    if is_postgres():
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT chat_id, message_id FROM appointment_admin_messages
                WHERE appointment_id = $1;
            """, appointment_id)
            return [dict(r) for r in rows]
    else:
        async with aiosqlite.connect(DATABASE_NAME) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT chat_id, message_id FROM appointment_admin_messages
                WHERE appointment_id = ?
            """, (appointment_id,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]


async def save_anonymous_question(
    user_id: int,
    question_text: str,
    username: str | None = None,
    full_name: str | None = None
) -> int:
    """Shifokorga savolni bazaga kiritish"""
    if is_postgres():
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            q_id = await conn.fetchval("""
                INSERT INTO questions (user_id, username, full_name, question_text, status)
                VALUES ($1, $2, $3, $4, 'Yangi')
                RETURNING id;
            """, user_id, username or "", full_name or "", question_text)
            return q_id
    else:
        async with aiosqlite.connect(DATABASE_NAME) as db:
            cursor = await db.execute("""
                INSERT INTO questions (user_id, username, full_name, question_text, status)
                VALUES (?, ?, ?, ?, 'Yangi')
            """, (user_id, username or "", full_name or "", question_text))
            await db.commit()
            return cursor.lastrowid


async def get_question_by_id(question_id: int) -> dict | None:
    """Savolni ID bo'yicha olish"""
    if is_postgres():
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM questions WHERE id = $1;", question_id)
            return dict(row) if row else None
    else:
        async with aiosqlite.connect(DATABASE_NAME) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM questions WHERE id = ?", (question_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None


async def update_question_answered(question_id: int, answer_text: str, answered_by: str):
    """Savolga javob berilganini bazada belgilash"""
    if is_postgres():
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE questions
                SET status = 'answered', answer_text = $1, answered_by = $2
                WHERE id = $3;
            """, answer_text, answered_by, question_id)
    else:
        async with aiosqlite.connect(DATABASE_NAME) as db:
            await db.execute("""
                UPDATE questions
                SET status = 'answered', answer_text = ?, answered_by = ?
                WHERE id = ?
            """, (answer_text, answered_by, question_id))
            await db.commit()


async def save_admin_question_message(question_id: int, chat_id: int, message_id: int):
    """Adminlarga yuborilgan savol xabarini saqlash"""
    if is_postgres():
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO question_admin_messages (question_id, chat_id, message_id)
                VALUES ($1, $2, $3);
            """, question_id, chat_id, message_id)
    else:
        async with aiosqlite.connect(DATABASE_NAME) as db:
            await db.execute("""
                INSERT INTO question_admin_messages (question_id, chat_id, message_id)
                VALUES (?, ?, ?)
            """, (question_id, chat_id, message_id))
            await db.commit()


async def get_admin_question_messages(question_id: int) -> list[dict]:
    """Savolga tegishli barcha admin xabarlarini olish"""
    if is_postgres():
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT chat_id, message_id FROM question_admin_messages
                WHERE question_id = $1;
            """, question_id)
            return [dict(r) for r in rows]
    else:
        async with aiosqlite.connect(DATABASE_NAME) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT chat_id, message_id FROM question_admin_messages
                WHERE question_id = ?
            """, (question_id,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]


# ==========================================
# DINAMIK ADMINLAR BOSHQARUVI
# ==========================================
async def get_admin_permissions(user_id: int) -> dict | None:
    """Foydalanuvchi admin ekanligini va uning huquqlarini olish (Super Admin har doim to'liq huquqli)"""
    if user_id in ADMIN_IDS:
        return {
            "user_id": user_id,
            "is_super": True,
            "can_manage_appointments": True,
            "can_reply_questions": True,
            "can_view_stats": True,
            "can_broadcast": True,
            "can_manage_admins": True,
        }

    if is_postgres():
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM admins WHERE user_id = $1;", user_id)
            if not row:
                return None
            d = dict(row)
    else:
        async with aiosqlite.connect(DATABASE_NAME) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM admins WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None
                d = dict(row)

    return {
        "user_id": int(d["user_id"]),
        "full_name": d.get("full_name") or "",
        "is_super": False,
        "can_manage_appointments": bool(d.get("can_manage_appointments")),
        "can_reply_questions": bool(d.get("can_reply_questions")),
        "can_view_stats": bool(d.get("can_view_stats")),
        "can_broadcast": bool(d.get("can_broadcast")),
        "can_manage_admins": bool(d.get("can_manage_admins")),
    }


async def get_all_admins() -> list[dict]:
    """Bazadagi barcha qo'shilgan adminlarni olish"""
    if is_postgres():
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM admins ORDER BY created_at ASC;")
            return [dict(r) for r in rows]
    else:
        async with aiosqlite.connect(DATABASE_NAME) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM admins ORDER BY created_at ASC") as cursor:
                return [dict(r) for r in await cursor.fetchall()]


async def get_admins_with_permission(perm_col: str) -> list[int]:
    """Muayyan huquqqa ega barcha admin ID larini olish (Super Adminlar bilan birga)"""
    allowed_cols = {
        "can_manage_appointments",
        "can_reply_questions",
        "can_view_stats",
        "can_broadcast",
        "can_manage_admins",
    }
    if perm_col not in allowed_cols:
        return list(ADMIN_IDS)

    result = set(ADMIN_IDS)
    if is_postgres():
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(f"SELECT user_id FROM admins WHERE {perm_col} = TRUE;")
            for r in rows:
                result.add(int(r["user_id"]))
    else:
        async with aiosqlite.connect(DATABASE_NAME) as db:
            async with db.execute(f"SELECT user_id FROM admins WHERE {perm_col} = 1") as cursor:
                for r in await cursor.fetchall():
                    result.add(int(r[0]))
    return list(result)


async def upsert_admin(user_id: int, full_name: str, added_by: int, perms: dict):
    """Yangi admin qo'shish yoki mavjud admin huquqlarini yangilash"""
    c_app = bool(perms.get("can_manage_appointments", False))
    c_q = bool(perms.get("can_reply_questions", False))
    c_st = bool(perms.get("can_view_stats", False))
    c_br = bool(perms.get("can_broadcast", False))
    c_ad = bool(perms.get("can_manage_admins", False))

    if is_postgres():
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO admins (
                    user_id, full_name, added_by,
                    can_manage_appointments, can_reply_questions,
                    can_view_stats, can_broadcast, can_manage_admins
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT(user_id) DO UPDATE SET
                    full_name = EXCLUDED.full_name,
                    added_by = EXCLUDED.added_by,
                    can_manage_appointments = EXCLUDED.can_manage_appointments,
                    can_reply_questions = EXCLUDED.can_reply_questions,
                    can_view_stats = EXCLUDED.can_view_stats,
                    can_broadcast = EXCLUDED.can_broadcast,
                    can_manage_admins = EXCLUDED.can_manage_admins;
            """, user_id, full_name, added_by, c_app, c_q, c_st, c_br, c_ad)
    else:
        async with aiosqlite.connect(DATABASE_NAME) as db:
            await db.execute("""
                INSERT INTO admins (
                    user_id, full_name, added_by,
                    can_manage_appointments, can_reply_questions,
                    can_view_stats, can_broadcast, can_manage_admins
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    full_name = excluded.full_name,
                    added_by = excluded.added_by,
                    can_manage_appointments = excluded.can_manage_appointments,
                    can_reply_questions = excluded.can_reply_questions,
                    can_view_stats = excluded.can_view_stats,
                    can_broadcast = excluded.can_broadcast,
                    can_manage_admins = excluded.can_manage_admins
            """, (user_id, full_name, added_by, int(c_app), int(c_q), int(c_st), int(c_br), int(c_ad)))
            await db.commit()


async def delete_admin(user_id: int) -> bool:
    """Dinamik adminni o'chirish (Super Adminlar o'chirilmaydi)"""
    if user_id in ADMIN_IDS:
        return False

    if is_postgres():
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            res = await conn.execute("DELETE FROM admins WHERE user_id = $1;", user_id)
            return res.endswith("1")
    else:
        async with aiosqlite.connect(DATABASE_NAME) as db:
            cursor = await db.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
            await db.commit()
            return cursor.rowcount > 0


async def get_appointments_stats() -> dict:
    """Statistika: jami foydalanuvchilar, bugungi va jami arizalar soni"""
    if is_postgres():
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            users_count = await conn.fetchval("SELECT COUNT(*) FROM users;") or 0
            total_apps = await conn.fetchval("SELECT COUNT(*) FROM appointments;") or 0
            today_apps = await conn.fetchval("""
                SELECT COUNT(*) FROM appointments 
                WHERE DATE(created_at) = CURRENT_DATE;
            """) or 0
            pending_apps = await conn.fetchval("""
                SELECT COUNT(*) FROM appointments WHERE status = 'Kutilmoqda';
            """) or 0
            return {
                "total_users": users_count,
                "total_appointments": total_apps,
                "today_appointments": today_apps,
                "pending_appointments": pending_apps
            }
    else:
        async with aiosqlite.connect(DATABASE_NAME) as db:
            async with db.execute("SELECT COUNT(*) FROM users") as cursor:
                users_count = (await cursor.fetchone())[0]

            async with db.execute("SELECT COUNT(*) FROM appointments") as cursor:
                total_apps = (await cursor.fetchone())[0]

            async with db.execute("""
                SELECT COUNT(*) FROM appointments 
                WHERE date(created_at, 'localtime') = date('now', 'localtime')
            """) as cursor:
                today_apps = (await cursor.fetchone())[0]

            async with db.execute("""
                SELECT COUNT(*) FROM appointments WHERE status = 'Kutilmoqda'
            """) as cursor:
                pending_apps = (await cursor.fetchone())[0]

            return {
                "total_users": users_count,
                "total_appointments": total_apps,
                "today_appointments": today_apps,
                "pending_appointments": pending_apps
            }


async def log_user_event(user_id: int, username: str | None, full_name: str | None, step_name: str):
    """Foydalanuvchi bosgan tugma yoki o'tgan bosqichni analitika uchun saqlash"""
    if is_postgres():
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO user_events (user_id, username, full_name, step_name)
                VALUES ($1, $2, $3, $4);
            """, user_id, username or "", full_name or "", step_name)
    else:
        async with aiosqlite.connect(DATABASE_NAME) as db:
            await db.execute("""
                INSERT INTO user_events (user_id, username, full_name, step_name)
                VALUES (?, ?, ?, ?)
            """, (user_id, username or "", full_name or "", step_name))
            await db.commit()


async def get_funnel_analytics() -> dict:
    """Bo'limlar faolligi va qabulga yozilish voronkasi (drop-off) statistikasi"""
    if is_postgres():
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT step_name, COUNT(*) AS total_clicks, COUNT(DISTINCT user_id) AS unique_users
                FROM user_events
                GROUP BY step_name;
            """)
    else:
        async with aiosqlite.connect(DATABASE_NAME) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT step_name, COUNT(*) AS total_clicks, COUNT(DISTINCT user_id) AS unique_users
                FROM user_events
                GROUP BY step_name
            """) as cursor:
                rows = [dict(r) for r in await cursor.fetchall()]

    stats_map = {
        r["step_name"]: {
            "total": int(r["total_clicks"] or 0),
            "unique": int(r["unique_users"] or 0)
        }
        for r in rows
    }

    menu_keys = [
        "start",
        "menu_price",
        "menu_booking",
        "menu_services",
        "menu_doctor",
        "menu_location",
        "menu_anon_question"
    ]
    menu_stats = {k: stats_map.get(k, {"total": 0, "unique": 0}) for k in menu_keys}

    funnel_keys = [
        "step_1_disease",
        "step_2_name",
        "step_3_phone",
        "step_4_date",
        "step_5_time",
        "step_6_confirmed"
    ]
    funnel_stats = {k: stats_map.get(k, {"total": 0, "unique": 0})["unique"] for k in funnel_keys}

    # Eng ko'p yo'qotish (drop-off) qaysi bosqichda yuz berganini aniqlash
    biggest_dropoff = None
    max_dropped = 0
    for i in range(len(funnel_keys) - 1):
        curr_key = funnel_keys[i]
        next_key = funnel_keys[i + 1]
        curr_val = funnel_stats[curr_key]
        next_val = funnel_stats[next_key]
        dropped = max(0, curr_val - next_val)
        if curr_val > 0 and dropped > max_dropped:
            max_dropped = dropped
            biggest_dropoff = {
                "from_step": curr_key,
                "to_step": next_key,
                "dropped_count": dropped,
                "dropped_pct": round((dropped / curr_val) * 100, 1)
            }

    return {
        "menu_stats": menu_stats,
        "funnel_stats": funnel_stats,
        "biggest_dropoff": biggest_dropoff
    }


async def export_appointments_to_excel(filepath: str) -> str:
    """
    Barcha arizalar ro'yxatini chiroyli, ustun kengliklari avtomatik moslangan,
    sarlavhalari qalin va rangli qilib tartiblangan .xlsx fayl sifatida saqlash.
    """
    if is_postgres():
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            records = await conn.fetch("""
                SELECT id, created_at, notes, patient_name, phone_number, service, status
                FROM appointments
                ORDER BY id DESC;
            """)
            rows = [dict(r) for r in records]
    else:
        async with aiosqlite.connect(DATABASE_NAME) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("""
                SELECT id, created_at, notes, patient_name, phone_number, service, status
                FROM appointments
                ORDER BY id DESC
            """) as cursor:
                rows = [dict(r) for r in await cursor.fetchall()]

    wb = Workbook()
    ws = wb.active
    ws.title = "Arizalar"

    headers = [
        "№",
        "ID",
        "Ariza yuborilgan vaqt",
        "Belgilangan qabul vaqti",
        "Bemor F.I.Sh",
        "Telefon raqami",
        "Tanlangan muammo",
        "Holati"
    ]
    ws.append(headers)

    header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    
    thin_border = Border(
        left=Side(style='thin', color='D9D9D9'),
        right=Side(style='thin', color='D9D9D9'),
        top=Side(style='thin', color='D9D9D9'),
        bottom=Side(style='thin', color='D9D9D9')
    )
    zebra_fill = PatternFill(start_color="F9FAFB", end_color="F9FAFB", fill_type="solid")
    white_fill = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")

    for col_num in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_num)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    row_index = 1
    for row in rows:
        row_index += 1
        current_fill = zebra_fill if row_index % 2 == 0 else white_fill
        
        # created_at formatlash
        created_val = row.get("created_at")
        if isinstance(created_val, datetime):
            created_str = created_val.strftime("%d.%m.%Y %H:%M")
        else:
            created_str = str(created_val or "")[:16]

        ws.append([
            row_index - 1,
            row.get("id"),
            created_str,
            row.get("notes"),
            row.get("patient_name"),
            row.get("phone_number"),
            row.get("service"),
            row.get("status")
        ])

        for col_num in range(1, len(headers) + 1):
            cell = ws.cell(row=row_index, column=col_num)
            cell.font = Font(name="Calibri", size=11)
            cell.border = thin_border
            cell.fill = current_fill
            
            if col_num in (1, 2, 3, 4, 6, 8):
                cell.alignment = Alignment(horizontal="center", vertical="center")
            else:
                cell.alignment = Alignment(horizontal="left", vertical="center")

    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            val_str = str(cell.value or "")
            if len(val_str) > max_len:
                max_len = len(val_str)
        ws.column_dimensions[col_letter].width = max(max_len + 4, 14)

    ws.row_dimensions[1].height = 28
    wb.save(filepath)
    return filepath
