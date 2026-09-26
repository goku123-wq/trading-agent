"""Market-hours stop-loss / target check. Run every few minutes between 9:15 AM and 3:30 PM IST.

Reads state/stops.json (written by run_daily.py) and sends a Telegram alert the first time a
position's latest price crosses its stop or target. Uses Yahoo 1-minute data, which can lag
by a few minutes; a broker feed (Angel One / Upstox) is the upgrade for tick-level alerts.
"""
import logging
import sys
from datetime import datetime, time, timezone, timedelta
from pathlib import Path

from agent.notify import send_telegram
from agent.positions import Position, check, load_json, save_json

ROOT = Path(__file__).parent
STATE = ROOT / "state"
IST = timezone(timedelta(hours=5, minutes=30))
log = logging.getLogger(__name__)


def market_open(now: datetime) -> bool:
    return now.weekday() < 5 and time(9, 15) <= now.time() <= time(15, 30)


def latest_prices(symbols: list[str], period: str = "1d") -> dict[str, tuple[float, float, float]]:
    """(low, high, last) per symbol for the latest session from 1-minute bars."""
    import pandas as pd
    import yfinance as yf

    tickers = [f"{s}.NS" for s in symbols]
    raw = yf.download(tickers, period=period, interval="1m", group_by="ticker", progress=False)
    out = {}
    for sym, tk in zip(symbols, tickers):
        try:
            df = (raw[tk] if isinstance(raw.columns, pd.MultiIndex) else raw).dropna()
        except KeyError:
            continue
        if not df.empty:
            df = df[df.index.date == df.index[-1].date()]  # last session only
            out[sym] = (float(df["Low"].min()), float(df["High"].max()), float(df["Close"].iloc[-1]))
    return out


def run(positions, prices, alerted, day):
    alerts = []
    for p in positions:
        if p.symbol not in prices:
            continue
        a = check(p, *prices[p.symbol])
        if a is None:
            continue
        key = a.key if a.kind != "NEAR STOP" else f"{a.key}:{day}"
        if key not in alerted:
            alerted[key] = day
            alerts.append(a)
    return alerts


def test_run(positions) -> None:
    """Replay the last trading session: report every position's day range vs its levels."""
    prices = latest_prices([p.symbol for p in positions], period="5d")
    alerts = run(positions, prices, {}, "test")
    lines = ["🧪 TEST: stop-loss check on the last trading session", ""]
    for p in positions:
        if p.symbol in prices:
            low, high, last = prices[p.symbol]
            lines.append(f"• {p.symbol}: last {last:.2f} (day {low:.2f}-{high:.2f}) | SL {p.stop} | T {p.target or '-'}")
    lines += ["", "Would have alerted:"] + ([a.text() for a in alerts] or ["• nothing, all within their levels"])
    msg = "\n".join(lines)
    print(msg)
    send_telegram(msg)


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    now = datetime.now(IST)
    if "--test" in sys.argv:
        test_run([Position(**p) for p in load_json(STATE / "stops.json", [])])
        return
    if not market_open(now):
        log.info("market closed (%s IST); nothing to do", f"{now:%a %H:%M}")
        return
    positions = [Position(**p) for p in load_json(STATE / "stops.json", [])]
    if not positions:
        log.info("no positions to watch")
        return
    alerted = load_json(STATE / "alerted.json", {})
    alerts = run(positions, latest_prices([p.symbol for p in positions]), alerted, f"{now:%Y-%m-%d}")
    if alerts:
        send_telegram("⏰ Live check " + f"{now:%H:%M}" + " IST\n" + "\n".join(a.text() for a in alerts))
        save_json(STATE / "alerted.json", alerted)
    log.info("%d positions checked, %d new alerts", len(positions), len(alerts))


if __name__ == "__main__":
    main()
