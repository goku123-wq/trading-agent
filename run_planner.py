"""Morning Telegram planner.

    python run_planner.py --ask --listen 85   # 8:00 AM: ask, then answer replies live until ~9:25
    python run_planner.py                     # answer any waiting replies once and exit
"""
import argparse
import json
import logging
import os
import time
from pathlib import Path

from agent.notify import get_updates, send_telegram
from agent.planner import ASK, HELP, answer, parse_request
from agent.positions import load_json, save_json

ROOT = Path(__file__).parent
STATE = ROOT / "state" / "telegram.json"
log = logging.getLogger(__name__)


def handle(updates: list[dict], chat_id: str, ideas: dict) -> list[str]:
    """Replies to send for the owner's new messages (other chats are ignored)."""
    replies = []
    for u in updates:
        msg = u.get("message") or {}
        if str(msg.get("chat", {}).get("id")) != chat_id:
            continue
        text = msg.get("text", "")
        if text.strip().lower() in ("/start", "start"):
            replies.append(ASK)
            continue
        req = parse_request(text)
        replies.append(answer(ideas, *req) if req else HELP)
    return replies


def poll_once(state: dict, chat_id: str, wait: int = 0) -> int:
    updates = get_updates(state.get("offset"), wait)
    if not updates:
        return 0
    path = ROOT / "docs" / "ideas.json"
    ideas = json.loads(path.read_text()) if path.exists() else {}
    for text in handle(updates, chat_id, ideas):
        send_telegram(text)
    state["offset"] = max(u["update_id"] for u in updates) + 1
    save_json(STATE, state)
    return len(updates)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ask", action="store_true", help="send the morning question first")
    ap.add_argument("--listen", type=float, default=0, help="keep answering replies for this many minutes")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    chat_id = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()
    state = load_json(STATE, {})
    if args.ask:
        old = get_updates(state.get("offset"))  # skip anything sent before the question
        if old:
            state["offset"] = max(u["update_id"] for u in old) + 1
            save_json(STATE, state)
        send_telegram(ASK)
    deadline = time.monotonic() + args.listen * 60
    handled = poll_once(state, chat_id)
    while time.monotonic() < deadline:
        handled += poll_once(state, chat_id, wait=int(min(25, max(1, deadline - time.monotonic()))))
    log.info("%d messages handled", handled)


if __name__ == "__main__":
    main()
