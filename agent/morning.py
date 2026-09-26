"""10 AM market check: market mood plus opening-range (9:15-10:00) setups. Not financial advice.

Works on 5-minute bars for today (Open/High/Low/Close/Volume, IST timestamps) and the
daily frame with indicators from agent.indicators.add_indicators.
"""
from dataclasses import dataclass
from datetime import time
from typing import Optional

import pandas as pd

from agent.report import line, sizing_note
from agent.signals import Suggestion, _r

OR_END = time(10, 0)  # opening range = 9:15 to 10:00


@dataclass
class IndexMove:
    name: str
    last: float
    change_pct: float
    from_open_pct: float


def index_move(name: str, prev_close: float, bars: pd.DataFrame) -> IndexMove:
    last, opened = float(bars["Close"].iloc[-1]), float(bars["Open"].iloc[0])
    return IndexMove(name, round(last, 2), round((last / prev_close - 1) * 100, 2),
                     round((last / opened - 1) * 100, 2))


def mood(nifty: Optional[IndexMove], vix: Optional[IndexMove], advancers: int, decliners: int) -> str:
    """One word for the morning: Bullish, Bearish or Mixed."""
    score = 0
    if nifty:
        score += 1 if nifty.change_pct > 0.3 else -1 if nifty.change_pct < -0.3 else 0
        score += 1 if nifty.from_open_pct > 0.1 else -1 if nifty.from_open_pct < -0.1 else 0
    if vix and vix.change_pct > 5:
        score -= 1
    total = advancers + decliners
    if total:
        breadth = advancers / total
        score += 1 if breadth >= 0.65 else -1 if breadth <= 0.35 else 0
    return "Bullish" if score >= 2 else "Bearish" if score <= -2 else "Mixed"


def vwap(bars: pd.DataFrame) -> pd.Series:
    typical = (bars["High"] + bars["Low"] + bars["Close"]) / 3
    vol = bars["Volume"].replace(0, 1)
    return (typical * vol).cumsum() / vol.cumsum()


def opening_range_setup(symbol: str, bars: pd.DataFrame, daily: pd.DataFrame,
                        market: str = "Mixed") -> Optional[Suggestion]:
    """Price already outside the opening range, on the right side of VWAP and the daily trend."""
    if len(daily) < 60 or bars.empty:
        return None
    orng = bars[bars.index.time < OR_END]
    if len(orng) < 3:
        return None
    orh, orl = float(orng["High"].max()), float(orng["Low"].min())
    last = float(bars["Close"].iloc[-1])
    vw = float(vwap(bars).iloc[-1])
    d = daily.iloc[-1]
    prev_close = float(d["Close"])
    atr = float(d["ATR14"])
    gap_pct = (float(bars["Open"].iloc[0]) / prev_close - 1) * 100
    reasons = [f"gap {gap_pct:+.1f}%"] if abs(gap_pct) >= 0.5 else []

    if last > orh and last > vw and prev_close > d["EMA20"] and market != "Bearish":
        stop = max(orl, vw - 0.25 * atr)
        if last - stop > 0.8 * atr:  # too far from support; chasing
            return None
        reasons += ["broke above 9:15-10:00 high", "above VWAP", "daily trend up"]
        risk = last - stop
        score = 60 + (10 if market == "Bullish" else 0) + (10 if gap_pct > 0 else 0)
        return Suggestion(symbol, "10am", "BUY", _r(last), _r(stop), _r(last + 1.5 * risk), score, reasons)

    if last < orl and last < vw and prev_close < d["EMA20"] and market != "Bullish":
        stop = min(orh, vw + 0.25 * atr)
        if stop - last > 0.8 * atr:
            return None
        reasons += ["broke below 9:15-10:00 low", "below VWAP", "daily trend down"]
        risk = stop - last
        score = 60 + (10 if market == "Bearish" else 0) + (10 if gap_pct < 0 else 0)
        return Suggestion(symbol, "10am", "SELL", _r(last), _r(stop), _r(last - 1.5 * risk), score, reasons)
    return None


def triggered(s: Suggestion, bars: pd.DataFrame) -> bool:
    """Did yesterday's 'BUY above' / 'SELL below' level get crossed this morning?"""
    if s.action == "BUY above":
        return float(bars["High"].max()) >= s.entry
    if s.action == "SELL below":
        return float(bars["Low"].min()) <= s.entry
    return False


def to_telegram(day, market, nifty, bank, vix, adv, dec, setups, trig, limit=6) -> str:
    def idx(m):
        return f"{m.name} {m.last} ({m.change_pct:+.2f}%)" if m else ""

    lines = [f"🔔 10 AM market check {day:%d %b}", f"Mood: {market}",
             " | ".join(x for x in (idx(nifty), idx(bank), idx(vix)) if x),
             f"Watchlist breadth: {adv} up / {dec} down", ""]
    lines.append("Setups now:")
    for title, cap in (("Large caps:", "Large"), ("Mid caps:", "Mid"), ("Watchlist:", "Watch")):
        group = [s for s in setups if s.cap == cap][:limit]
        if group:
            lines += [title] + [line(s, why=True) for s in group]
    rest = [s for s in setups if s.cap not in ("Large", "Mid", "Watch")][:limit]
    lines += [line(s, why=True) for s in rest]
    if not setups:
        lines.append("• none, better to wait")
    if trig:
        lines += ["", "Yesterday's levels triggered:"] + [f"• {s.symbol} {s.action} {s.entry}" for s in trig]
    lines += ["", sizing_note(), "Intraday: square off by 3:15 PM. Not financial advice."]
    return "\n".join(lines)
