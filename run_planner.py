"""Telegram planner bot.

    python run_planner.py --serve 5.5         # always-on: answer live, ask at 8 AM, start due workflows
    python run_planner.py --ask --listen 15   # test: ask now, then answer replies live for 15 minutes
    python run_planner.py                     # answer any waiting replies once and exit
"""
import argparse
import json
import logging
import os
import time
from pathlib import Path

import requests

from agent import clock
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


def start_workflow(name: str) -> bool:
    """Start another workflow of this repo (needs GITHUB_TOKEN with actions: write)."""
    token, repo = os.getenv("GITHUB_TOKEN"), os.getenv("GITHUB_REPOSITORY")
    if not token or not repo:
        log.info("Not on GitHub Actions; would start %s", name)
        return False
    try:
        r = requests.post(f"https://api.github.com/repos/{repo}/actions/workflows/{name}/dispatches",
                          headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
                          json={"ref": os.getenv("GITHUB_REF_NAME") or "main"}, timeout=20)
    except requests.RequestException as e:
        log.error("Could not start %s: %s", name, e)
        return False
    if not r.ok:
        log.error("Could not start %s: %s %s", name, r.status_code, r.text[:200])
    return r.ok


def run_due(state: dict, now=None) -> list[str]:
    """Send the 8 AM question and start workflows whose time has come; returns what ran."""
    now = now or clock.now_ist()
    done = state.setdefault("done", {})
    ran = []
    for job, key in clock.due(now, done):
        ok = send_telegram(ASK) if job == "ask" else start_workflow(job)
        log.info("%s %s: %s", now.strftime("%H:%M"), job, "ok" if ok else "failed")
        done[key] = ok or "failed"  # don't retry every loop; the next slot/day runs again
        ran.append(job)
    if ran:
        state["done"] = clock.prune(done, now)
        save_json(STATE, state)
    return ran


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ask", action="store_true", help="send the morning question first")
    ap.add_argument("--listen", type=float, default=0, help="keep answering replies for this many minutes")
    ap.add_argument("--serve", type=float, default=0, help="always-on mode for this many hours")
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
    deadline = time.monotonic() + (args.serve * 3600 or args.listen * 60)
    if args.serve:
        run_due(state)
    handled = poll_once(state, chat_id)
    while time.monotonic() < deadline:
        handled += poll_once(state, chat_id, wait=int(min(25, max(1, deadline - time.monotonic()))))
        if args.serve:
            run_due(state)
    log.info("%d messages handled", handled)


if __name__ == "__main__":
    main()
