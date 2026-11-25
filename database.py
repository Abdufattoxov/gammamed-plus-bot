import os
import aiosqlite
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from config import DATABASE_NAME, DATABASE_URL

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


async def save_anonymous_question(user_id: int, question_text: str) -> int:
    """Anonim savolni bazaga kiritish"""
    if is_postgres():
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            q_id = await conn.fetchval("""
                INSERT INTO questions (user_id, question_text, status)
                VALUES ($1, $2, 'Yangi')
                RETURNING id;
            """, user_id, question_text)
            return q_id
    else:
        async with aiosqlite.connect(DATABASE_NAME) as db:
            cursor = await db.execute("""
                INSERT INTO questions (user_id, question_text, status)
                VALUES (?, ?, 'Yangi')
            """, (user_id, question_text))
            await db.commit()
            return cursor.lastrowid


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
