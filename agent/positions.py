"""Positions to watch for stop-loss / target alerts.

Two sources:
- Your own holdings: config/positions.csv, or the POSITIONS_CSV env var (use a GitHub secret
  if the repo is public and you don't want holdings visible). Leave `stop` blank to get a
  trailing stop (2x ATR below the highest close of the last 20 days).
- BUY suggestions from the daily report, tracked automatically until stop or target is hit.

The daily run writes the effective levels to state/stops.json; the market-hours check reads it.
"""
import csv
import io
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

NEAR_STOP_PCT = 1.0  # warn when price is within this % of the stop


@dataclass
class Position:
    symbol: str
    entry: float
    stop: Optional[float]
    target: Optional[float] = None
    side: str = "LONG"  # LONG or SHORT
    source: str = "manual"  # manual or report
    opened: str = ""


def _num(x) -> Optional[float]:
    x = (x or "").strip()
    return float(x) if x else None


def parse_csv(text: str) -> list[Position]:
    rows = csv.DictReader(io.StringIO(text), skipinitialspace=True)
    out = []
    for r in rows:
        sym = (r.get("symbol") or "").strip().upper()
        if not sym or sym.startswith("#"):
            continue
        out.append(Position(sym, _num(r.get("entry")) or 0.0, _num(r.get("stop")), _num(r.get("target")),
                            (r.get("side") or "LONG").strip().upper()))
    return out


def load_manual(path: Path) -> list[Position]:
    text = os.getenv("POSITIONS_CSV") or (path.read_text() if path.exists() else "")
    return parse_csv(text)


def load_json(path: Path, default):
    return json.loads(path.read_text()) if path.exists() else default


def save_json(path: Path, obj) -> None:
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def load_tracked(path: Path) -> list[Position]:
    return [Position(**p) for p in load_json(path, [])]


def save_tracked(path: Path, positions: list[Position]) -> None:
    save_json(path, [asdict(p) for p in positions])


def trailing_stop(df, mult: float = 2.0) -> float:
    return round(float(df["Close"].iloc[-20:].max() - mult * df["ATR14"].iloc[-1]), 2)


@dataclass
class Alert:
    symbol: str
    kind: str  # STOP HIT, TARGET HIT, NEAR STOP
    price: float
    level: float
    source: str

    @property
    def key(self) -> str:
        return f"{self.symbol}:{self.kind}:{self.level}"

    def text(self) -> str:
        icon = {"STOP HIT": "🔴", "TARGET HIT": "🟢", "NEAR STOP": "🟠"}[self.kind]
        verb = {"STOP HIT": "hit stop-loss", "TARGET HIT": "hit target", "NEAR STOP": "is near stop-loss"}[self.kind]
        tag = "your position" if self.source == "manual" else "report idea"
        return f"{icon} {self.symbol} {verb} {self.level} (price {self.price}, {tag})"


def check(position: Position, low: float, high: float, last: float) -> Optional[Alert]:
    """Compare a price bar (use low=high=last for a single quote) against the levels."""
    p, long = position, position.side == "LONG"
    if p.stop is not None and ((long and low <= p.stop) or (not long and high >= p.stop)):
        return Alert(p.symbol, "STOP HIT", round(last, 2), p.stop, p.source)
    if p.target is not None and ((long and high >= p.target) or (not long and low <= p.target)):
        return Alert(p.symbol, "TARGET HIT", round(last, 2), p.target, p.source)
    if p.stop is not None and abs(last - p.stop) / p.stop * 100 <= NEAR_STOP_PCT:
        return Alert(p.symbol, "NEAR STOP", round(last, 2), p.stop, p.source)
    return None
