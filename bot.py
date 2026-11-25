import asyncio
import logging
import os
import sys
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from config import BOT_TOKEN
import database
from handlers import router


async def health_check_handler(request: web.Request) -> web.Response:
    """Render va boshqa bulutli serverlar uchun sog'lomlik tekshiruvi (Health Check)"""
    return web.Response(text="Gammamed Plus Telegram Bot is running!", status=200)


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
    """Telegram menyusida chiqadigan standart buyruqlar"""
    commands = [
        BotCommand(command="start", description="Botni qayta ishga tushirish va asosiy menyu"),
        BotCommand(command="admin", description="Klinika boshqaruv paneli (faqat ma'murlar uchun)")
    ]
    await bot.set_my_commands(commands)


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

    logger.info("«Gammamed Plus» tibbiyot boti muvaffaqiyatli ishga tushirildi!")

    try:
        # Eski kutilgan yangilanishlarni tashlab yuborish
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        if web_runner:
            await web_runner.cleanup()
        await bot.session.close()
        logger.info("Bot to'xtatildi.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot to'xtatildi.")
