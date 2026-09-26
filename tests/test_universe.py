from agent.report import to_markdown, to_telegram
from agent.signals import Suggestion
from agent.universe import load_universe, parse_index_csv


def test_parse_index_csv():
    text = "Company Name,Industry,Symbol,Series,ISIN Code\nReliance,Oil,RELIANCE,EQ,INE002A01018\nX,Y,m&m,EQ,Z\n"
    assert parse_index_csv(text) == ["RELIANCE", "M&M"]


def test_load_universe_labels_and_watchlist(tmp_path):
    (tmp_path / "largecap.txt").write_text("# header\nRELIANCE\nTCS\n")
    (tmp_path / "midcap.txt").write_text("PERSISTENT\n")
    (tmp_path / "watchlist.txt").write_text("TCS\nIRFC\n")
    assert load_universe(tmp_path) == {"RELIANCE": "Large", "TCS": "Large", "PERSISTENT": "Mid", "IRFC": "Watch"}


def test_load_universe_watchlist_only(tmp_path):
    (tmp_path / "watchlist.txt").write_text("INFY\n")
    assert load_universe(tmp_path) == {"INFY": "Watch"}


def test_report_shows_cap():
    import datetime
    big = Suggestion("BIG", "long-term", "BUY", 100, 90, 120, 80, ["r"], cap="Large")
    mid = Suggestion("MIDDY", "long-term", "BUY", 50, 45, 60, 80, ["r"], cap="Mid")
    day = datetime.date(2026, 9, 28)
    md = to_markdown(day, [big, mid], [], [])
    assert "| 80 | Large | r |" in md
    assert "| BIG | BUY | 100 | 90 | 120 | 125 | ₹12.5k | ₹2.5k | ₹1.2k | Large |" in md
    msg = to_telegram(day, [big, mid], [])
    assert "Long-term basket (~₹5.0k" in msg and "[L] BIG" in msg and "[M] MIDDY" in msg
