import os
import aiosqlite
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from config import DATABASE_NAME


async def init_db():
    """Ma'lumotlar bazasi va jadvallarni yaratish"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        # Foydalanuvchilar jadvali
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                full_name TEXT,
                username TEXT,
                phone TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Qabulga yozilish arizalari jadvali
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

        # Anonim savollar jadvali
        await db.execute("""
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                question_text TEXT,
                status TEXT DEFAULT 'Yangi',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()


async def register_user(user_id: int, full_name: str, username: str | None, phone: str | None = None):
    """Foydalanuvchini ro'yxatdan o'tkazish yoki ma'lumotlarini yangilash"""
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
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def get_all_user_ids() -> list[int]:
    """Barcha foydalanuvchilar ID larini olish (xabar tarqatish uchun)"""
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
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute("""
            INSERT INTO appointments (user_id, service, region, patient_name, phone_number, notes, status)
            VALUES (?, ?, ?, ?, ?, ?, 'Kutilmoqda')
        """, (user_id, service, region, patient_name, phone_number, full_notes))
        await db.commit()
        return cursor.lastrowid


async def get_appointment_by_id(app_id: int) -> dict | None:
    """Arizani ID bo'yicha olish"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM appointments WHERE id = ?", (app_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def update_appointment_status(app_id: int, status: str):
    """Ariza holatini yangilash (Qabul qilindi / Qo'ng'iroq qilindi / Bekor qilindi)"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("""
            UPDATE appointments
            SET status = ?
            WHERE id = ?
        """, (status, app_id))
        await db.commit()


async def save_anonymous_question(user_id: int, question_text: str) -> int:
    """Anonim savolni bazaga kiritish"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        cursor = await db.execute("""
            INSERT INTO questions (user_id, question_text, status)
            VALUES (?, ?, 'Yangi')
        """, (user_id, question_text))
        await db.commit()
        return cursor.lastrowid


async def get_appointments_stats() -> dict:
    """Statistika: jami foydalanuvchilar, bugungi va jami arizalar soni"""
    async with aiosqlite.connect(DATABASE_NAME) as db:
        # Jami foydalanuvchilar
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            users_count = (await cursor.fetchone())[0]

        # Jami arizalar
        async with db.execute("SELECT COUNT(*) FROM appointments") as cursor:
            total_apps = (await cursor.fetchone())[0]

        # Bugungi arizalar (DATE(created_at) = DATE('now', 'localtime'))
        async with db.execute("""
            SELECT COUNT(*) FROM appointments 
            WHERE date(created_at, 'localtime') = date('now', 'localtime')
        """) as cursor:
            today_apps = (await cursor.fetchone())[0]

        # Kutilayotgan arizalar
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
    async with aiosqlite.connect(DATABASE_NAME) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT id, created_at, notes, patient_name, phone_number, service, status
            FROM appointments
            ORDER BY id DESC
        """) as cursor:
            rows = await cursor.fetchall()

    wb = Workbook()
    ws = wb.active
    ws.title = "Arizalar"

    # Sarlavhalar
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

    # Uslub berish: Sarlavha qatori (Navy ko'k rang, qalin oq yozuv)
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

    # Qatorlarni kiritish
    row_index = 1
    for row in rows:
        row_index += 1
        current_fill = zebra_fill if row_index % 2 == 0 else white_fill
        
        ws.append([
            row_index - 1,
            row["id"],
            row["created_at"],
            row["notes"],
            row["patient_name"],
            row["phone_number"],
            row["service"],
            row["status"]
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

    # Ustun kengliklarini avtomatik moslashtirish
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
