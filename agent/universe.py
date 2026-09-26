"""Which stocks to scan, and whether each is a large cap or a mid cap.

- config/largecap.txt: Nifty 100 constituents
- config/midcap.txt:   Nifty Midcap 150 constituents
- config/watchlist.txt: your extra picks (tagged "Watch" unless already in one of the above)

Refresh the index lists with `python update_universe.py` (a weekly GitHub Action does this).
If the index files are missing, only the watchlist is scanned.
"""
import csv
import io
from pathlib import Path

import requests

from agent.data import load_watchlist

INDEX_CSVS = {
    "largecap.txt": "ind_nifty100list.csv",
    "midcap.txt": "ind_niftymidcap150list.csv",
}
SOURCES = [
    "https://niftyindices.com/IndexConstituent/{}",
    "https://nsearchives.nseindia.com/content/indices/{}",
]
LABELS = {"largecap.txt": "Large", "midcap.txt": "Mid"}


def load_universe(config: Path) -> dict[str, str]:
    caps: dict[str, str] = {}
    for fname, label in LABELS.items():
        path = config / fname
        if path.exists():
            for s in load_watchlist(path):
                caps.setdefault(s, label)
    watch = config / "watchlist.txt"
    if watch.exists():
        for s in load_watchlist(watch):
            caps.setdefault(s, "Watch")
    return caps


def parse_index_csv(text: str) -> list[str]:
    rows = csv.DictReader(io.StringIO(text))
    return [r["Symbol"].strip().upper() for r in rows if (r.get("Symbol") or "").strip()]


def download_index(csv_name: str) -> list[str]:
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "text/csv,*/*"}
    last_err = None
    for src in SOURCES:
        try:
            r = requests.get(src.format(csv_name), headers=headers, timeout=30)
            r.raise_for_status()
            syms = parse_index_csv(r.text)
            if len(syms) >= 50:
                return syms
            last_err = f"only {len(syms)} symbols from {src}"
        except Exception as e:  # try the next mirror
            last_err = e
    raise RuntimeError(f"could not download {csv_name}: {last_err}")
