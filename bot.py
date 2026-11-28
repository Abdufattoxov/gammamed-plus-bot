import asyncio
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeDefault, BotCommandScopeChat

from config import BOT_TOKEN, ADMIN_IDS, CLINIC_ADDRESS, CLINIC_REMAINING_AMOUNT
import database
from handlers import router, send_reception_list, _fmt_money
from webhook_server import start_web_server

UZ_TZ = timezone(timedelta(hours=5))


async def keep_alive_task():
    """
    Render bepul (Free) tarifida 15 daqiqa tashqi HTTP so'rov kelmasa, serverni avtomatik
    'uyqu' (spin down / sleep) rejimiga tushirib qo'yadi.
    Ushbu vazifa har 10 daqiqada o'ziga o'zi HTTP so'rov yuborib turadi va serverni 24/7 uyg'oq saqlaydi.
    """
    import aiohttp
    app_url = os.getenv("RENDER_EXTERNAL_URL", "https://gammamed-plus-bot.onrender.com").rstrip("/")
    # Server to'liq yuklanib olishi uchun dastlabki 45 soniya kutamiz
    await asyncio.sleep(45)
    logging.info(f"Keep-alive self-ping xizmati ishga tushirildi: {app_url}/health")

    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{app_url}/health", timeout=15) as resp:
                    logging.info(f"Keep-alive self-ping muvaffaqiyatli: status={resp.status}")
        except Exception as e:
            logging.warning(f"Keep-alive self-ping ogohlantirish: {e}")
        # Har 10 daqiqada (600 soniya) qaytarish (Render 15 daqiqada uxlaydi, shuning uchun 10 daqiqa ideal)
        await asyncio.sleep(600)


async def set_bot_commands(bot: Bot):
    """Oddiy foydalanuvchilarga faqat /start, adminlarga esa /start va /admin ko'rinadi"""
    default_commands = [
        BotCommand(command="start", description="Botni qayta ishga tushirish va asosiy menyu")
    ]
    await bot.set_my_commands(default_commands, scope=BotCommandScopeDefault())

    admin_commands = [
        BotCommand(command="start", description="Botni qayta ishga tushirish va asosiy menyu"),
        BotCommand(command="admin", description="Klinika boshqaruv paneli (faqat ma'murlar uchun)")
    ]
    all_admin_ids = set(ADMIN_IDS)
    try:
        dynamic_admins = await database.get_all_admins()
        for adm in dynamic_admins:
            all_admin_ids.add(int(adm["user_id"]))
    except Exception:
        pass

    for admin_id in all_admin_ids:
        try:
            await bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=admin_id))
        except Exception as e:
            logging.warning(f"Admin {admin_id} uchun komandalar menyusini o'rnatishda xatolik: {e}")


async def reception_and_reminder_scheduler(bot: Bot):
    """
    O'zbekiston vaqti (UTC+5) bo'yicha fon rejalashtiruvchisi:
    1. Har kuni 08:30 da bugungi tasdiqlangan mijozlar ro'yxatini (xabar + .xlsx) barcha adminlarga yuboradi.
    2. Har 15 daqiqada qabul vaqtiga 2 soat qolgan mijozlarga avtomatik eslatma yuboradi.
    """
    await asyncio.sleep(30)
    last_daily_report_date = None
    last_reminder_check_ts = 0.0

    while True:
        try:
            now_uz = datetime.now(UZ_TZ)
            today_str = now_uz.strftime("%Y-%m-%d")

            # 1. Har kuni 08:30 dan boshlab bugungi resepshn ro'yxatini yuborish
            if now_uz.hour == 8 and now_uz.minute >= 30 and last_daily_report_date != today_str:
                last_daily_report_date = today_str
                target_admins = await database.get_admins_with_permission("can_manage_appointments")
                for adm_id in target_admins:
                    try:
                        await send_reception_list(
                            bot=bot,
                            target_chat_id=adm_id,
                            target_dates=[today_str],
                            title_label=f"Ertalabki Resepshn ro‘yxati ({today_str})"
                        )
                    except Exception as e:
                        logging.warning(f"08:30 resepshn ro'yxati yuborishda xatolik ({adm_id}): {e}")

            # 2. Har 15 daqiqada 2 soatlik eslatmalarni tekshirish
            loop_ts = asyncio.get_running_loop().time()
            if loop_ts - last_reminder_check_ts >= 900 or last_reminder_check_ts == 0.0:
                last_reminder_check_ts = loop_ts
                unreminded = await database.get_paid_unreminded_appointments()
                for app in unreminded:
                    date_iso = (app.get("appointment_date_iso") or "").strip()
                    slot = (app.get("appointment_slot") or "").strip()
                    if not date_iso or not slot:
                        continue
                    try:
                        start_hhmm = slot.split("-")[0].strip()
                        appt_dt = datetime.strptime(f"{date_iso} {start_hhmm}", "%Y-%m-%d %H:%M").replace(tzinfo=UZ_TZ)
                        diff_sec = (appt_dt - now_uz).total_seconds()
                        # Qabulga 2 soat (0 < diff <= 7200 soniya) qolganda eslatma yuborish
                        if 0 < diff_sec <= 7200:
                            rem = _fmt_money(CLINIC_REMAINING_AMOUNT)
                            num = app.get("client_number") or "-"
                            reminder_text = (
                                f"⏰ <b>Eslatma! Bugun Dr. Zarifa qabulidasiz.</b>\n\n"
                                f"🎫 <b>Tartib raqamingiz:</b> № {num}\n"
                                f"🕒 <b>Qabul vaqti:</b> Bugun soat {slot}\n"
                                f"📍 <b>Manzil:</b> {CLINIC_ADDRESS}\n"
                                f"💵 <b>Resepshn uchun qoldiq to‘lov:</b> {rem} so‘m.\n\n"
                                f"<i>(Barcha eski analiz va UTT qog‘ozlaringizni olishni unutmang. Sizni kutamiz!)</i>"
                            )
                            try:
                                await bot.send_message(chat_id=app["user_id"], text=reminder_text)
                                await database.mark_reminder_sent(app["id"])
                            except Exception:
                                pass
                    except Exception:
                        continue
        except Exception as e:
            logging.warning(f"Scheduler siklida xatolik: {e}")

        # 08:30 oynasini o'tkazib yubormaslik uchun har 60 soniyada uyg'onadi
        await asyncio.sleep(60)


async def main():
    # Logging sozlamalari
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    logger = logging.getLogger(__name__)

    if not BOT_TOKEN:
        logger.error(
            "Xatolik: BOT_TOKEN topilmadi! .env faylida bot tokeningizni ko'rsatganingizga ishonch hosil qiling."
        )
        return

    # Bot va Dispatcher obyektlari
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Routerni ulash
    dp.include_router(router)

    # Ma'lumotlar bazasini initsializatsiya qilish
    logger.info("Ma'lumotlar bazasi initsializatsiya qilinmoqda...")
    await database.init_db()

    # Render va ChatPlace webhook uchun fonga aiohttp veb-serverni ulash
    web_runner = await start_web_server(bot)

    # Buyruqlar menyusini o'rnatish
    await set_bot_commands(bot)

    # Render serverini 24/7 uyg'oq (uyqusiz) ushlab turish uchun fonga self-ping vazifasini qo'shamiz
    keep_alive_bg_task = asyncio.create_task(keep_alive_task())
    scheduler_bg_task = asyncio.create_task(reception_and_reminder_scheduler(bot))

    logger.info("«Gammamed Plus» tibbiyot boti muvaffaqiyatli ishga tushirildi!")

    try:
        # Eski kutilgan yangilanishlarni tashlab yuborish
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        keep_alive_bg_task.cancel()
        scheduler_bg_task.cancel()
        if web_runner:
            await web_runner.cleanup()
        await bot.session.close()
        logger.info("Bot to'xtatildi.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot to'xtatildi.")
