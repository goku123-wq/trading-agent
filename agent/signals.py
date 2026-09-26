"""Rule-based trade suggestions. Not financial advice.

Two horizons:
- long_term_signal: positional ideas (weeks to months) from trend + momentum.
- intraday_setup:   levels to watch for the next session (breakout / breakdown).
"""
import math
import os
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

MIN_BARS = 210  # need SMA200 plus some history


def profit_goal() -> float:
    """Rupees you want to make if a target is hit. Set PROFIT_GOAL (GitHub variable) to change."""
    try:
        return float(os.getenv("PROFIT_GOAL") or 10000)
    except ValueError:
        return 10000.0


@dataclass
class Suggestion:
    symbol: str
    horizon: str  # "long-term" or "intraday"
    action: str  # "BUY", "SELL/EXIT", "BUY above", "SELL below"
    entry: float
    stop: float
    target: float
    score: int
    reasons: list = field(default_factory=list)
    cap: str = ""  # Large / Mid / Watch

    def sizing(self, goal: Optional[float] = None) -> Optional[tuple[int, float, float]]:
        """(quantity, capital needed, loss if stop hits) so the target makes about `goal` rupees."""
        move = abs(self.target - self.entry)
        if self.action == "SELL/EXIT" or move <= 0:
            return None
        qty = math.ceil((goal or profit_goal()) / move)
        return qty, round(qty * self.entry, 2), round(qty * abs(self.entry - self.stop), 2)

    @property
    def risk_reward(self) -> float:
        risk = abs(self.entry - self.stop)
        return round(abs(self.target - self.entry) / risk, 2) if risk else 0.0


def _r(x: float) -> float:
    return round(float(x), 2)


def long_term_signal(symbol: str, df: pd.DataFrame) -> Optional[Suggestion]:
    """Buy pullbacks in established uptrends; flag exits when the trend breaks."""
    if len(df) < MIN_BARS:
        return None
    t, y = df.iloc[-1], df.iloc[-2]
    close, atr = t["Close"], t["ATR14"]
    uptrend = close > t["SMA200"] and t["SMA50"] > t["SMA200"]

    # Exit / avoid: trend broke today, or death cross today.
    crossed_below_200 = y["Close"] >= y["SMA200"] and close < t["SMA200"]
    death_cross = y["SMA50"] >= y["SMA200"] and t["SMA50"] < t["SMA200"]
    if crossed_below_200 or death_cross:
        reasons = []
        if crossed_below_200:
            reasons.append("closed below 200-day average")
        if death_cross:
            reasons.append("50-day average crossed below 200-day")
        return Suggestion(symbol, "long-term", "SELL/EXIT", _r(close), _r(close + 2 * atr),
                          _r(close - 4 * atr), 60 + 20 * len(reasons), reasons)

    if not uptrend:
        return None

    score, reasons = 40, ["uptrend: price and 50-day above 200-day average"]
    near_ema = abs(close - t["EMA20"]) <= 1.0 * atr or abs(close - t["SMA50"]) <= 1.0 * atr
    if near_ema:
        score += 20
        reasons.append("pulled back near 20-day/50-day average")
    if 45 <= t["RSI14"] <= 65 and t["RSI14"] > y["RSI14"]:
        score += 20
        reasons.append(f"RSI {t['RSI14']:.0f} and turning up")
    if close > t["Open"] and t["Volume"] > t["VOL20"]:
        score += 10
        reasons.append("up day on above-average volume")
    if t["RSI14"] > 75:
        score -= 30
        reasons.append(f"overbought (RSI {t['RSI14']:.0f}), wait for a dip")

    if score < 70:
        return None
    stop = min(close - 2 * atr, t["SMA50"] - 0.5 * atr)
    target = close + 2 * (close - stop)
    return Suggestion(symbol, "long-term", "BUY", _r(close), _r(stop), _r(target), score, reasons)


def intraday_setup(symbol: str, df: pd.DataFrame) -> Optional[Suggestion]:
    """Next-session breakout levels after a tight day (NR7 / inside day) or a volume surge."""
    if len(df) < MIN_BARS:
        return None
    t, y = df.iloc[-1], df.iloc[-2]
    atr = t["ATR14"]
    reasons, score = [], 0

    if t["RANGE"] <= df["RANGE"].iloc[-7:].min():
        score += 30
        reasons.append("narrowest range of last 7 days (NR7)")
    if t["High"] <= y["High"] and t["Low"] >= y["Low"]:
        score += 20
        reasons.append("inside day")
    if t["Volume"] >= 2 * t["VOL20"]:
        score += 25
        reasons.append(f"volume {t['Volume'] / t['VOL20']:.1f}x the 20-day average")
    if score < 30:
        return None

    buffer = 0.1 * atr
    if t["Close"] > t["EMA20"] and t["Close"] > t["SMA50"]:
        entry = t["High"] + buffer
        stop = max(t["Low"], entry - 1.0 * atr)
        target = entry + 1.5 * (entry - stop)
        action, trend = "BUY above", "trend up (above 20 and 50-day averages)"
    elif t["Close"] < t["EMA20"] and t["Close"] < t["SMA50"]:
        entry = t["Low"] - buffer
        stop = min(t["High"], entry + 1.0 * atr)
        target = entry - 1.5 * (stop - entry)
        action, trend = "SELL below", "trend down (below 20 and 50-day averages)"
    else:
        return None
    reasons.append(trend)
    return Suggestion(symbol, "intraday", action, _r(entry), _r(stop), _r(target), score + 20, reasons)
