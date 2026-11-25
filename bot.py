import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand

from config import BOT_TOKEN
import database
from handlers import router


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
        await bot.session.close()
        logger.info("Bot to'xtatildi.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot to'xtatildi.")
