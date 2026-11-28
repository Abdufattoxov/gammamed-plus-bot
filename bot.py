import asyncio
import logging
import os
import sys
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeDefault, BotCommandScopeChat

from config import BOT_TOKEN, ADMIN_IDS
import database
from handlers import router


async def health_check_handler(request: web.Request) -> web.Response:
    """Render va boshqa bulutli serverlar uchun sog'lomlik tekshiruvi (Health Check)"""
    return web.Response(text="Gammamed Plus Telegram Bot is running!", status=200)


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


async def start_background_web_server():
    """
    Render 'Web Service' sifatida ishlatilganda PORT o'zgaruvchisini tinglaydi.
    Shu tariqa Render botni muvaffaqiyatli 'Live' holatiga o'tkazadi.
    """
    port_env = os.getenv("PORT")
    if not port_env:
        return None

    try:
        port = int(port_env)
        app = web.Application()
        app.router.add_get("/", health_check_handler)
        app.router.add_get("/health", health_check_handler)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        logging.info(f"Render uchun Health Check veb-serveri 0.0.0.0:{port} manzilida ishga tushirildi.")
        return runner
    except Exception as e:
        logging.warning(f"Veb-serverni ishga tushirishda xatolik: {e}")
        return None


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
    for admin_id in ADMIN_IDS:
        try:
            await bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=admin_id))
        except Exception as e:
            logging.warning(f"Admin {admin_id} uchun komandalar menyusini o'rnatishda xatolik: {e}")


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

    # Render uchun fonga veb-serverni ulash
    web_runner = await start_background_web_server()

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

    # Buyruqlar menyusini o'rnatish
    await set_bot_commands(bot)

    # Render serverini 24/7 uyg'oq (uyqusiz) ushlab turish uchun fonga self-ping vazifasini qo'shamiz
    keep_alive_bg_task = asyncio.create_task(keep_alive_task())

    logger.info("«Gammamed Plus» tibbiyot boti muvaffaqiyatli ishga tushirildi!")

    try:
        # Eski kutilgan yangilanishlarni tashlab yuborish
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        keep_alive_bg_task.cancel()
        if web_runner:
            await web_runner.cleanup()
        await bot.session.close()
        logger.info("Bot to'xtatildi.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot to'xtatildi.")
