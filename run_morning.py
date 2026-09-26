"""10 AM market check. Run once at ~10:00 AM IST on trading days.

    python run_morning.py            # send to Telegram
    python run_morning.py --no-send
"""
import argparse
import json
import logging
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd

from agent import morning
from agent.data import fetch_daily
from agent.export import write_ideas
from agent.indicators import add_indicators
from agent.notify import send_telegram
from agent.signals import Suggestion
from agent.universe import load_universe

ROOT = Path(__file__).parent
IST = timezone(timedelta(hours=5, minutes=30))
INDICES = {"NIFTY 50": "^NSEI", "BANK NIFTY": "^NSEBANK", "INDIA VIX": "^INDIAVIX"}
log = logging.getLogger(__name__)


def fetch_intraday(tickers: list[str]) -> dict[str, pd.DataFrame]:
    """Today's 5-minute bars in IST, keyed by the ticker passed in."""
    import yfinance as yf

    raw = yf.download(tickers, period="5d", interval="5m", group_by="ticker", progress=False)
    today = datetime.now(IST).date()
    out = {}
    for tk in tickers:
        try:
            df = (raw[tk] if isinstance(raw.columns, pd.MultiIndex) else raw).dropna()
        except KeyError:
            continue
        if df.empty:
            continue
        df.index = df.index.tz_convert("Asia/Kolkata") if df.index.tz else df.index.tz_localize("Asia/Kolkata")
        df = df[df.index.date == today]
        if not df.empty:
            out[tk] = df
    return out


def load_previous_intraday(path: Path) -> list[Suggestion]:
    """Parse the intraday table from the last daily report (reports/latest.md)."""
    if not path.exists():
        return []
    text = path.read_text().split("## Intraday watchlist", 1)[-1]
    out = []
    for m in re.finditer(r"^\| (\S+) \| (BUY above|SELL below) \| ([\d.]+) \| ([\d.]+) \| ([\d.]+) \|", text, re.M):
        out.append(Suggestion(m[1], "intraday", m[2], float(m[3]), float(m[4]), float(m[5]), 0))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=ROOT / "config", type=Path)
    ap.add_argument("--no-send", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    caps = load_universe(args.config)
    symbols = list(caps)
    intraday = fetch_intraday([f"{s}.NS" for s in symbols] + list(INDICES.values()))
    if not any(tk.endswith(".NS") for tk in intraday):
        log.info("no trading data for today (holiday or weekend); nothing to send")
        return
    daily = {s: add_indicators(df) for s, df in fetch_daily(symbols + list(INDICES.values()), period="1y").items()}

    def prev_close(key):  # last completed daily bar before today
        df = daily.get(key)
        if df is None:
            return None
        today = datetime.now(IST).date()
        df = df[df.index.date < today]
        return float(df["Close"].iloc[-1]) if len(df) else None

    moves = {}
    for name, tk in INDICES.items():
        pc = prev_close(tk)
        if tk in intraday and pc:
            moves[name] = morning.index_move(name, pc, intraday[tk])

    adv = dec = 0
    for s in symbols:
        pc, bars = prev_close(s), intraday.get(f"{s}.NS")
        if pc and bars is not None:
            adv += bars["Close"].iloc[-1] > pc
            dec += bars["Close"].iloc[-1] < pc
    market = morning.mood(moves.get("NIFTY 50"), moves.get("INDIA VIX"), adv, dec)

    today = datetime.now(IST).date()
    setups = []
    for s in symbols:
        bars, d = intraday.get(f"{s}.NS"), daily.get(s)
        if bars is None or d is None:
            continue
        d = d[d.index.date < today]  # yesterday's close and trend, not today's partial bar
        if (x := morning.opening_range_setup(s, bars, d, market)):
            x.cap = caps.get(s, "")
            setups.append(x)
    setups.sort(key=lambda x: -x.score)

    trig = [p for p in load_previous_intraday(ROOT / "reports" / "latest.md")
            if f"{p.symbol}.NS" in intraday and morning.triggered(p, intraday[f"{p.symbol}.NS"])]

    msg = morning.to_telegram(today, market, moves.get("NIFTY 50"), moves.get("BANK NIFTY"),
                              moves.get("INDIA VIX"), adv, dec, setups, trig)
    print(msg)
    write_ideas(ROOT / "docs" / "ideas.json", "morning", today, {"setups": setups}, {"mood": market})
    if not args.no_send:
        send_telegram(msg)
    log.info("mood %s, %d setups, %d triggered", market, len(setups), len(trig))


if __name__ == "__main__":
    main()
