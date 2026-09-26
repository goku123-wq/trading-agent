"""Download the current Nifty 100 and Nifty Midcap 150 lists into config/."""
import logging
from datetime import date
from pathlib import Path

from agent.universe import INDEX_CSVS, download_index

ROOT = Path(__file__).parent

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    for fname, csv_name in INDEX_CSVS.items():
        syms = download_index(csv_name)
        header = f"# {csv_name} from NSE, updated {date.today()}. Regenerated weekly; edit watchlist.txt instead.\n"
        (ROOT / "config" / fname).write_text(header + "\n".join(syms) + "\n")
        logging.info("%s: %d symbols", fname, len(syms))
