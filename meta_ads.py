import asyncio
import os
import aiohttp
from config import META_ACCESS_TOKEN, META_AD_ACCOUNT_ID, USD_TO_UZS


class MetaAuthError(Exception):
    """Meta API tokeni yo'q yoki muddati tugagan holat"""
    pass


def _extract_link_clicks(row: dict) -> int:
    """Insights qatoridan link_click sonini ajratib olish (bo'lmasa clicks ga tayanadi)"""
    actions = row.get("actions") or []
    for act in actions:
        if act.get("action_type") == "link_click":
            try:
                return int(float(act.get("value", 0)))
            except (ValueError, TypeError):
                pass
    try:
        return int(float(row.get("clicks", 0)))
    except (ValueError, TypeError):
        return 0


def _parse_insight_row(row: dict | None) -> dict:
    """Meta Insights API bitta qatorini toza sonlarga o'girish"""
    if not row:
        return {
            "ad_name": "",
            "spend": 0.0,
            "impressions": 0,
            "reach": 0,
            "link_clicks": 0,
            "cpc": 0.0,
            "ctr": 0.0,
        }

    spend = float(row.get("spend") or 0)
    impressions = int(float(row.get("impressions") or 0))
    reach = int(float(row.get("reach") or 0))
    link_clicks = _extract_link_clicks(row)
    cpc = (spend / link_clicks) if link_clicks > 0 else float(row.get("cpc") or 0)
    ctr = float(row.get("ctr") or 0)

    return {
        "ad_name": row.get("ad_name", ""),
        "spend": spend,
        "impressions": impressions,
        "reach": reach,
        "link_clicks": link_clicks,
        "cpc": cpc,
        "ctr": ctr,
    }


async def _fetch_insights(session: aiohttp.ClientSession, url: str, params: dict) -> list[dict]:
    """Meta Graph API insights so'rovini yuborish va xatolarni ushlash"""
    async with session.get(url, params=params, timeout=20) as resp:
        payload = await resp.json()
        if resp.status != 200 or "error" in payload:
            err = payload.get("error", {})
            code = err.get("code")
            if resp.status in (401, 403) or code in (190, 102, 10):
                raise MetaAuthError(err.get("message", "Invalid or expired Meta token"))
            raise RuntimeError(err.get("message", f"Meta API HTTP {resp.status}"))
        return payload.get("data", [])


async def get_meta_ads_report(total_appointments: int, total_starts: int) -> str:
    """
    Meta Graph API v21.0 orqali umumiy, bugungi va har bir video reklama bo'yicha
    natijalarni olib, sodda o'zbek tilida hisobot tayyorlash.
    """
    token = os.getenv("META_ACCESS_TOKEN", META_ACCESS_TOKEN)
    account_id = os.getenv("META_AD_ACCOUNT_ID", META_AD_ACCOUNT_ID)
    rate = int(os.getenv("USD_TO_UZS", str(USD_TO_UZS)))

    if not token:
        raise MetaAuthError("META_ACCESS_TOKEN kiritilmagan")

    base_url = f"https://graph.facebook.com/v21.0/act_{account_id}/insights"
    fields_base = "spend,impressions,reach,clicks,actions,cpc,ctr"
    fields_ad = "ad_name,spend,impressions,reach,clicks,actions,cpc,ctr"

    async with aiohttp.ClientSession() as session:
        overall_data, today_data, ads_data = await asyncio.gather(
            _fetch_insights(session, base_url, {
                "access_token": token,
                "date_preset": "maximum",
                "fields": fields_base,
            }),
            _fetch_insights(session, base_url, {
                "access_token": token,
                "date_preset": "today",
                "fields": fields_base,
            }),
            _fetch_insights(session, base_url, {
                "access_token": token,
                "level": "ad",
                "date_preset": "maximum",
                "fields": fields_ad,
            }),
        )

    overall = _parse_insight_row(overall_data[0] if overall_data else None)
    today = _parse_insight_row(today_data[0] if today_data else None)

    ads_parsed = [_parse_insight_row(r) for r in ads_data]
    video_1 = next((a for a in ads_parsed if "Video_1_DrZarifa_Ozi" in a["ad_name"]), _parse_insight_row(None))
    video_2 = next((a for a in ads_parsed if "Video_2_Bulungur_Diktor" in a["ad_name"]), _parse_insight_row(None))

    def fmt_int(val: int) -> str:
        return f"{val:,}".replace(",", " ")

    def fmt_uzs(usd: float) -> str:
        return f"{fmt_int(round(usd * rate))} so‘m"

    meta_clicks = overall["link_clicks"]
    conv_pct = round((total_appointments / meta_clicks) * 100, 1) if meta_clicks > 0 else 0.0
    cost_per_lead = (overall["spend"] / total_appointments) if total_appointments > 0 else 0.0

    # Avtomatik auditor xulosasi
    conclusions = []
    if meta_clicks > 0 and conv_pct < 15.0:
        conclusions.append(
            "⚠️ Diqqat: Tugma bosganlar ko‘p, lekin botda raqam qoldirish 15% dan kam. Bot qadamlarini tekshiring!"
        )
    if overall["cpc"] > 0.15:
        conclusions.append(
            "⚠️ 1 ta klik narxi qimmatlashmoqda ($0.15+). Auditoriya yoki kreativni tekshiring."
        )
    if not conclusions:
        conclusions.append(
            "✅ Natijalar yaxshi! Operatorlar botga tushgan har bir raqamga 30 daqiqa ichida qo‘ng‘iroq qilishini nazorat qiling."
        )

    report = (
        f"📊 <b>TARGET REKLAMA TO‘LIQ NATIJALARI</b>\n\n"
        f"📅 <b>BUGUNGI KUN NATIJASI:</b>\n"
        f"• Sarflandi: <b>${today['spend']:.2f}</b> (~{fmt_uzs(today['spend'])})\n"
        f"• Ko‘rgan odamlar: <b>{fmt_int(today['reach'])} kishi</b>\n"
        f"• Tugma bosganlar (botga o‘tish): <b>{fmt_int(today['link_clicks'])} ta</b>\n"
        f"• 1 ta klik narxi: <b>${today['cpc']:.2f}</b> (~{fmt_uzs(today['cpc'])})\n\n"
        f"🌍 <b>UMUMIY NATIJA (Boshlanganidan beri):</b>\n"
        f"• Jami sarflangan pul: <b>${overall['spend']:.2f}</b> (~{fmt_uzs(overall['spend'])})\n"
        f"• Reklamani ko‘rgan odamlar: <b>{fmt_int(overall['reach'])} kishi</b> (jami {fmt_int(overall['impressions'])} marta ko‘rsatildi)\n"
        f"• Botga o‘tish tugmasini bosganlar: <b>{fmt_int(overall['link_clicks'])} ta</b>\n"
        f"• 1 ta tugma bosish narxi: <b>${overall['cpc']:.2f}</b> (~{fmt_uzs(overall['cpc'])})\n"
        f"• Reklama qiziqish darajasi (CTR): <b>{overall['ctr']:.2f}%</b>\n\n"
        f"🎬 <b>VIDEOLAR BO‘YICHA SOLISHTIRUV:</b>\n"
        f"1️⃣ <b>Dr. Zarifa o‘zi gapirgan video (<code>Video_1_DrZarifa_Ozi</code>):</b>\n"
        f"   • Sarflandi: <b>${video_1['spend']:.2f}</b> | Ko‘rish: <b>{fmt_int(video_1['reach'])}</b> | Klik: <b>{fmt_int(video_1['link_clicks'])} ta</b> | 1 klik: <b>${video_1['cpc']:.2f}</b>\n"
        f"2️⃣ <b>Diktorli video (<code>Video_2_Bulungur_Diktor</code>):</b>\n"
        f"   • Sarflandi: <b>${video_2['spend']:.2f}</b> | Ko‘rish: <b>{fmt_int(video_2['reach'])}</b> | Klik: <b>{fmt_int(video_2['link_clicks'])} ta</b> | 1 klik: <b>${video_2['cpc']:.2f}</b>\n\n"
        f"📥 <b>BOT VA MIJOZLAR KONVERSIYASI:</b>\n"
        f"• Tugma bosganlar (Meta): <b>{fmt_int(meta_clicks)} ta</b>\n"
        f"• Botga /start bosganlar (Baza): <b>{fmt_int(total_starts)} ta</b>\n"
        f"• Botga ariza qoldirganlar (Baza): <b>{fmt_int(total_appointments)} ta</b>\n"
        f"• Arizaga aylanish foizi: <b>{conv_pct:.1f}%</b>\n"
        f"• <b>1 ta tayyor mijoz (raqam) narxi:</b> <b>${cost_per_lead:.2f}</b> (~{fmt_uzs(cost_per_lead)})\n\n"
        f"💡 <b>AVTOMATIK AUDITOR XULOSASI:</b>\n"
        + "\n".join(conclusions)
    )
    return report
