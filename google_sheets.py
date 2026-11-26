import os
import logging
import aiohttp
from config import GOOGLE_SHEET_WEBHOOK_URL

logger = logging.getLogger(__name__)


async def append_lead_to_google_sheet(lead: dict) -> bool:
    """
    Yangi kelgan qabul arizasini Google Sheets'ga avtomatik qo'shish.
    lead: {
        "id": int,
        "date": str,
        "patient_name": str,
        "phone_number": str,
        "service": str,
        "appointment_time": str,
        "status": str,
        "user_id": int
    }
    """
    webhook_url = os.getenv("GOOGLE_SHEET_WEBHOOK_URL", GOOGLE_SHEET_WEBHOOK_URL)
    if not webhook_url:
        logger.info("Google Sheet webhook URL belgilanmagan, sinxronizatsiya o'tkazib yuborildi.")
        return False

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=lead, timeout=15) as resp:
                if resp.status == 200:
                    logger.info(f"Yangi ariza (#{lead.get('id')}) Google Sheets'ga muvaffaqiyatli qo'shildi.")
                    return True
                else:
                    text = await resp.text()
                    logger.warning(f"Google Sheets webhook javobi {resp.status}: {text}")
                    return False
    except Exception as e:
        logger.error(f"Google Sheets'ga yozishda xatolik: {e}")
        return False
