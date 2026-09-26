import datetime
import json

from agent.export import write_ideas
from agent.signals import Suggestion


def test_write_ideas_keeps_other_section(tmp_path):
    p = tmp_path / "ideas.json"
    a = Suggestion("A", "long-term", "BUY", 100, 95, 110, 80, ["r"], cap="Large")
    write_ideas(p, "daily", datetime.date(2026, 9, 25), {"long_term": [a], "intraday": []})
    write_ideas(p, "morning", datetime.date(2026, 9, 28), {"setups": [a]}, {"mood": "Mixed"})
    d = json.loads(p.read_text())
    assert d["daily"]["day"] == "2026-09-25" and d["daily"]["long_term"][0]["symbol"] == "A"
    assert d["morning"]["mood"] == "Mixed" and d["morning"]["setups"][0]["cap"] == "Large"
