"""Write ideas as JSON for the planner page (docs/index.html, served by GitHub Pages)."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

IST = timezone(timedelta(hours=5, minutes=30))


def idea(s) -> dict:
    return {"symbol": s.symbol, "action": s.action, "entry": s.entry, "stop": s.stop, "target": s.target,
            "score": s.score, "cap": s.cap, "reasons": list(s.reasons)}


def write_ideas(path: Path, section: str, day, ideas: dict, extra: dict | None = None) -> None:
    """Replace one section ("daily" or "morning") of the shared ideas file, keeping the other."""
    try:
        data = json.loads(path.read_text()) if path.exists() else {}
    except ValueError:
        data = {}
    data[section] = {"day": f"{day:%Y-%m-%d}", "generated": datetime.now(IST).isoformat(timespec="minutes"),
                     **{k: [idea(s) for s in v] for k, v in ideas.items()}, **(extra or {})}
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")
