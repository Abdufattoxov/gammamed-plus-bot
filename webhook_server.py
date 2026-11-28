import html
import logging
import os
import re
from aiohttp import web
from aiogram import Bot

from config import ADMIN_IDS, ADMIN_GROUP_ID, CHATPLACE_WEBHOOK_SECRET
import database
from keyboards import get_admin_appointment_kb

logger = logging.getLogger(__name__)


def normalize_phone(phone: str) -> str:
    """Telefon raqamni yagona +998XXXXXXXXX formatiga keltirish"""
    raw = str(phone or "").strip()
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 9:
        return f"+998{digits}"
    if len(digits) == 12 and digits.startswith("998"):
        return f"+{digits}"
    if raw.startswith("+") and len(digits) >= 9:
        return f"+{digits}"
    return raw or "Kiritilmagan"


def _verify_chatplace_secret(request: web.Request) -> bool:
    """Agar CHATPLACE_WEBHOOK_SECRET belgilangan bo'lsa, header yoki ?token= orqali tekshirish"""
    secret = os.getenv("CHATPLACE_WEBHOOK_SECRET", CHATPLACE_WEBHOOK_SECRET).strip()
    if not secret:
        return True

    token_query = request.query.get("token", "").strip()
    header_secret = (
        request.headers.get("X-ChatPlace-Secret")
        or request.headers.get("X-Webhook-Secret")
        or ""
    ).strip()
    auth_header = request.headers.get("Authorization", "").strip()
    bearer_token = auth_header[7:].strip() if auth_header.lower().startswith("bearer ") else ""

    return secret in (token_query, header_secret, bearer_token)


async def health_check_handler(request: web.Request) -> web.Response:
    """Render va boshqa bulutli serverlar uchun sog'lomlik tekshiruvi (Health Check)"""
    return web.Response(text="Gammamed Plus Telegram Bot is running!", status=200)


async def chatplace_webhook_handler(request: web.Request) -> web.Response:
    """
    ChatPlace.io Pro dan Instagram Direct arizalarini qabul qiluvchi webhook.
    Kutilayotgan JSON: {"name": "...", "phone": "...", "problem": "..."}
    """
    if not _verify_chatplace_secret(request):
        return web.json_response({"ok": False, "error": "Unauthorized"}, status=401)

    try:
        data = await request.json()
    except Exception:
        return web.json_response({"ok": False, "error": "Invalid JSON"}, status=400)

    name = str(data.get("name") or data.get("full_name") or "Noma'lum").strip()
    raw_phone = str(data.get("phone") or data.get("phone_number") or "Kiritilmagan").strip()
    phone = normalize_phone(raw_phone)
    problem = str(data.get("problem") or data.get("service") or "Ko'rsatilmagan").strip()

    try:
        # Oxirgi 24 soat ichida aynan shu telefon raqamdan ariza tushgan bo'lsa, dublikat ochmasdan yangilaymiz
        if phone != "Kiritilmagan":
            existing = await database.find_recent_appointment_by_phone(phone, hours=24)
            if existing:
                await database.update_chatplace_appointment(
                    app_id=existing["id"],
                    patient_name=name,
                    service=problem,
                    notes="Instagram Direct (ChatPlace - yangilandi)"
                )
                return web.json_response(
                    {"ok": True, "appointment_id": existing["id"], "deduplicated": True},
                    status=200
                )

        app_id = await database.create_appointment(
            user_id=0,
            service=problem,
            patient_name=name,
            phone_number=phone,
            appointment_time="Ma'muriyat belgilaydi",
            region="Bulung'ur",
            notes="Instagram Direct (ChatPlace)",
            source="Instagram (ChatPlace)"
        )
    except Exception as e:
        logger.error(f"ChatPlace arizasini bazaga saqlashda xatolik: {e}")
        return web.json_response({"ok": False, "error": "Database error"}, status=500)

    bot: Bot | None = request.app.get("bot")
    if bot:
        safe_name = html.escape(name)
        safe_phone = html.escape(phone)
        safe_problem = html.escape(problem)
        tel_clean = re.sub(r"[^\d+]", "", phone) or phone

        admin_text = (
            f"🆕 <b>Instagram Direct’dan yangi ariza (ChatPlace)!</b>\n"
            f"👤 <b>Ismi:</b> {safe_name}\n"
            f"📞 <b>Tel:</b> <a href=\"tel:{html.escape(tel_clean)}\">{safe_phone}</a>\n"
            f"🩺 <b>Muammo:</b> {safe_problem}\n"
            f"🆔 <b>Ariza:</b> #A-{app_id}"
        )

        target_chats: set[int] = set(ADMIN_IDS)
        try:
            perm_admins = await database.get_admins_with_permission("can_manage_appointments")
            target_chats.update(int(x) for x in perm_admins)
        except Exception:
            pass
        if ADMIN_GROUP_ID:
            target_chats.add(ADMIN_GROUP_ID)

        kb = get_admin_appointment_kb(app_id)
        for chat_id in target_chats:
            try:
                sent = await bot.send_message(chat_id=chat_id, text=admin_text, reply_markup=kb)
                await database.save_admin_appointment_message(app_id, chat_id, sent.message_id)
            except Exception as e:
                logger.warning(f"ChatPlace arizasini admin ({chat_id}) ga yuborishda xatolik: {e}")

    return web.json_response({"ok": True, "appointment_id": app_id}, status=200)


async def start_web_server(bot: Bot) -> web.AppRunner | None:
    """
    Bot bilan bir vaqtda ishlaydigan yengil aiohttp web-server.
    GET / va GET /health -> 200 OK
    POST /webhook/chatplace -> ChatPlace.io Pro webhook
    """
    port = int(os.getenv("PORT", 8080))
    try:
        app = web.Application()
        app["bot"] = bot
        app.router.add_get("/", health_check_handler)
        app.router.add_get("/health", health_check_handler)
        app.router.add_post("/webhook/chatplace", chatplace_webhook_handler)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        logger.info(f"Aiohttp web-server 0.0.0.0:{port} manzilida ishga tushirildi (/health, /webhook/chatplace).")
        return runner
    except Exception as e:
        logger.warning(f"Veb-serverni ishga tushirishda xatolik: {e}")
        return None
