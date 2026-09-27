"""Optional Telegram delivery. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to enable."""
import logging
import os

import requests

log = logging.getLogger(__name__)


def send_telegram(text: str) -> bool:
    token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    chat = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()
    if not token or not chat:
        log.info("Telegram not configured; skipping send")
        return False
    r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      json={"chat_id": chat, "text": text}, timeout=20)
    if not r.ok:
        log.error("Telegram send failed: %s %s", r.status_code, r.text[:200])
    return r.ok


def get_updates(offset: int | None = None, wait: int = 0) -> list[dict]:
    """New messages sent to the bot (Telegram keeps them for 24 hours until confirmed with offset).

    wait > 0 long-polls: the call returns as soon as a message arrives, or after `wait` seconds.
    """
    token = (os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    if not token:
        return []
    params = {"timeout": wait, "allowed_updates": '["message"]'}
    if offset is not None:
        params["offset"] = offset
    try:
        r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", params=params, timeout=wait + 20)
    except requests.RequestException as e:
        log.error("Telegram getUpdates error: %s", e)
        return []
    if not r.ok:
        log.error("Telegram getUpdates failed: %s %s", r.status_code, r.text[:200])
        return []
    return r.json().get("result", [])
