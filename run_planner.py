"""Morning Telegram planner.

    python run_planner.py --ask    # 8:00 AM: ask for capital and profit goal
    python run_planner.py          # every few minutes until 9:30: answer any replies
"""
import argparse
import json
import logging
import os
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ask", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if args.ask:
        send_telegram(ASK)
        return
    state = load_json(STATE, {})
    updates = get_updates(state.get("offset"))
    if not updates:
        log.info("no new messages")
        return
    ideas = json.loads((ROOT / "docs" / "ideas.json").read_text()) if (ROOT / "docs" / "ideas.json").exists() else {}
    chat_id = (os.getenv("TELEGRAM_CHAT_ID") or "").strip()
    for text in handle(updates, chat_id, ideas):
        send_telegram(text)
    state["offset"] = max(u["update_id"] for u in updates) + 1
    save_json(STATE, state)
    log.info("%d updates handled", len(updates))


if __name__ == "__main__":
    main()
