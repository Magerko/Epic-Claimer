"""Optional Telegram notifications for claim results and failures."""

import httpx
from loguru import logger

from settings import settings


async def notify(text: str) -> None:
    token = settings.TELEGRAM_BOT_TOKEN
    chat_id = settings.TELEGRAM_CHAT_ID
    if not token or not chat_id:
        return

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            await client.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": text},
            )
    except Exception as err:
        logger.debug(f"Telegram notify failed: {err}")
