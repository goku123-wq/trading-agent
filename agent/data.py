"""Free end-of-day data from Yahoo Finance (NSE symbols get a .NS suffix)."""
import logging
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)


def load_watchlist(path: Path) -> list[str]:
    lines = path.read_text().splitlines()
    return [s.strip().upper() for s in lines if s.strip() and not s.startswith("#")]


def fetch_daily(symbols: list[str], period: str = "2y") -> dict[str, pd.DataFrame]:
    import yfinance as yf

    tickers = [s if s.startswith("^") else f"{s}.NS" for s in symbols]  # ^ = index
    raw = yf.download(tickers, period=period, interval="1d", group_by="ticker",
                      auto_adjust=True, progress=False, threads=True)
    out = {}
    for sym, tk in zip(symbols, tickers):
        try:
            df = raw[tk] if isinstance(raw.columns, pd.MultiIndex) else raw
            df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
        except KeyError:
            df = pd.DataFrame()
        if df.empty:
            log.warning("no data for %s", sym)
            continue
        out[sym] = df
    return out
