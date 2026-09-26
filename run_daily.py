"""Build the end-of-day report. Run after market close (3:30 PM IST).

    python run_daily.py                 # uses config/watchlist.txt and config/positions.csv
    python run_daily.py --no-send       # write the report, skip Telegram
"""
import argparse
import logging
from dataclasses import asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

from agent.data import fetch_daily, load_watchlist
from agent.indicators import add_indicators
from agent.notify import send_telegram
from agent.positions import (Position, check, load_json, load_manual, load_tracked, save_json,
                             save_tracked, trailing_stop)
from agent.report import to_markdown, to_telegram
from agent.signals import intraday_setup, long_term_signal

ROOT = Path(__file__).parent
STATE = ROOT / "state"
IST = timezone(timedelta(hours=5, minutes=30))


def build(data):
    long_term, intraday = [], []
    for sym, df in data.items():
        if (s := long_term_signal(sym, df)):
            long_term.append(s)
        if (s := intraday_setup(sym, df)):
            intraday.append(s)
    # Don't suggest shorting intraday what we just called a long-term buy, or buying what we said to exit.
    lt = {s.symbol: s.action for s in long_term}
    intraday = [s for s in intraday
                if not (lt.get(s.symbol) == "BUY" and s.action == "SELL below")
                and not (lt.get(s.symbol) == "SELL/EXIT" and s.action == "BUY above")]
    long_term.sort(key=lambda s: (s.action != "BUY", -s.score))
    intraday.sort(key=lambda s: -s.score)
    return long_term, intraday


def review_positions(day: str, data, manual, tracked, new_buys, alerted):
    """Check today's bar against every position's levels. Returns alerts, rows, still-open tracked, watch list."""
    alerts, rows, still_open, watch = [], [], [], []
    for p in manual:
        df = data.get(p.symbol)
        if df is None:
            continue
        if p.stop is None:
            p.stop = trailing_stop(df)
        watch.append(p)
        rows.append((p, float(df["Close"].iloc[-1])))
    for p in tracked:
        if p.symbol in data:
            watch.append(p)
    for p in watch:
        t = data[p.symbol].iloc[-1]
        a = check(p, float(t["Low"]), float(t["High"]), float(t["Close"]))
        if a is None:
            if p.source == "report":
                still_open.append(p)
            continue
        if a.kind != "STOP HIT" and a.kind != "TARGET HIT" and p.source == "report":
            still_open.append(p)
        key = a.key if a.kind != "NEAR STOP" else f"{a.key}:{day}"
        if key not in alerted:
            alerted[key] = day
            alerts.append(a)
    open_syms = {p.symbol for p in still_open}
    for s in new_buys:
        if s.symbol not in open_syms:
            still_open.append(Position(s.symbol, s.entry, s.stop, s.target, "LONG", "report", day))
    return alerts, rows, still_open


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--watchlist", default=ROOT / "config" / "watchlist.txt", type=Path)
    ap.add_argument("--positions", default=ROOT / "config" / "positions.csv", type=Path)
    ap.add_argument("--no-send", action="store_true")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    manual = load_manual(args.positions)
    tracked = load_tracked(STATE / "tracked.json")
    symbols = load_watchlist(args.watchlist)
    wanted = list(dict.fromkeys(symbols + [p.symbol for p in manual + tracked]))
    data = {s: add_indicators(df) for s, df in fetch_daily(wanted).items()}
    if not data:
        raise SystemExit("No market data fetched; check network or symbols.")
    last_bar = max(df.index[-1] for df in data.values()).date()
    day = f"{last_bar:%Y-%m-%d}"

    long_term, intraday = build({s: data[s] for s in symbols if s in data})
    alerted = load_json(STATE / "alerted.json", {})
    buys = [s for s in long_term if s.action == "BUY"]
    alerts, rows, still_open = review_positions(day, data, manual, tracked, buys, alerted)

    save_tracked(STATE / "tracked.json", still_open)
    save_json(STATE / "alerted.json", alerted)
    watch = [asdict(p) for p, _ in rows] + [asdict(p) for p in still_open]
    save_json(STATE / "stops.json", watch)

    skipped = sorted(set(wanted) - set(data))
    md = to_markdown(last_bar, long_term, intraday, skipped, alerts, rows)
    out = ROOT / "reports" / f"{day}.md"
    out.parent.mkdir(exist_ok=True)
    out.write_text(md)
    (ROOT / "reports" / "latest.md").write_text(md)
    print(md)
    if not args.no_send:
        send_telegram(to_telegram(last_bar, long_term, intraday, alerts))
    logging.info("report written to %s (run at %s IST)", out, f"{datetime.now(IST):%H:%M}")


if __name__ == "__main__":
    main()
