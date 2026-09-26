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
    assert "| 80 | 500 | ₹50.0k | ₹5.0k | Large | r |" in md
    msg = to_telegram(day, [big, mid], [])
    assert msg.index("large caps:") < msg.index("[L] BIG") < msg.index("mid caps:") < msg.index("[M] MIDDY")
