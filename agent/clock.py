"""The bot's own clock: which jobs are due now (times in IST).

GitHub's cron often starts runs hours late or skips them, so the always-on Telegram bot keeps time
itself and starts the other workflows when they are due.
"""
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

# (job, weekdays, start time, how late it may still start)
DAILY = [
    ("ask", range(5), time(8, 0), timedelta(minutes=80)),                       # Telegram question
    ("morning-check.yml", range(5), time(10, 0), timedelta(minutes=60)),        # 10 AM market check
    ("daily-report.yml", range(5), time(17, 0), timedelta(hours=4)),            # evening report
    ("update-universe.yml", (6,), time(8, 30), timedelta(hours=12)),            # Sunday index refresh
]
STOPS = ("stop-check.yml", time(9, 15), time(15, 30), 10)  # every 10 min in market hours


def now_ist() -> datetime:
    return datetime.now(IST)


def due(now: datetime, done: dict) -> list[tuple[str, str]]:
    """(job, key) pairs that should run now and haven't run yet; `done` holds keys already run."""
    out = []
    day = now.date()
    for job, days, at, grace in DAILY:
        start = datetime.combine(day, at, IST)
        key = f"{job}@{day}"
        if now.weekday() in days and start <= now < start + grace and key not in done:
            out.append((job, key))
    job, first, last, every = STOPS
    open_, close = datetime.combine(day, first, IST), datetime.combine(day, last, IST)
    if now.weekday() < 5 and open_ <= now <= close:
        slot = int((now - open_).total_seconds() // (every * 60))
        key = f"{job}@{day}#{slot}"
        if key not in done:
            out.append((job, key))
    return out


def prune(done: dict, now: datetime, keep_days: int = 3) -> dict:
    """Drop keys older than a few days so the state file stays small."""
    cutoff = str(now.date() - timedelta(days=keep_days))
    return {k: v for k, v in done.items() if k.split("@", 1)[1][:10] >= cutoff}
