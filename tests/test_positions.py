import numpy as np

from agent.indicators import add_indicators
from agent.positions import Position, check, parse_csv, trailing_stop
from check_stops import run
from run_daily import review_positions
from tests.test_signals import make_df
from agent.signals import Suggestion


def test_parse_csv_skips_comments_and_blank_stop():
    ps = parse_csv("symbol,entry,stop,target,side\n# note\n# INFY,1,2,3,LONG\nrelIANCE,1380,,1500,\nTCS,3000,3100,2800,SHORT\n")
    assert [p.symbol for p in ps] == ["RELIANCE", "TCS"]
    assert ps[0].stop is None and ps[0].side == "LONG" and ps[1].side == "SHORT"


def test_check_long_and_short():
    long = Position("A", 100, 95, 110)
    assert check(long, 94, 101, 96).kind == "STOP HIT"
    assert check(long, 99, 111, 110).kind == "TARGET HIT"
    assert check(long, 95.5, 97, 95.5).kind == "NEAR STOP"
    assert check(long, 98, 102, 100) is None
    short = Position("B", 100, 105, 90, side="SHORT")
    assert check(short, 99, 106, 104).kind == "STOP HIT"
    assert check(short, 89, 101, 90).kind == "TARGET HIT"


def test_live_check_alerts_once():
    ps = [Position("A", 100, 95, 110), Position("B", 50, 45, 60)]
    alerted = {}
    first = run(ps, {"A": (94, 101, 94.5), "B": (49, 51, 50)}, alerted, "2026-09-28")
    assert [a.symbol for a in first] == ["A"]
    assert run(ps, {"A": (93, 101, 93)}, alerted, "2026-09-28") == []


def test_trailing_stop_below_recent_high():
    df = add_indicators(make_df(np.linspace(100, 200, 250)))
    ts = trailing_stop(df)
    assert ts < df["Close"].iloc[-1]


def test_review_positions_tracks_buys_and_closes_on_stop():
    df = add_indicators(make_df(np.linspace(100, 200, 250)))
    last = float(df["Close"].iloc[-1])
    data = {"UP": df, "HELD": df}
    tracked = [Position("UP", last + 20, last + 5, last + 50, source="report")]  # stop above today's low
    manual = [Position("HELD", 150, None)]
    buy = Suggestion("NEW", "long-term", "BUY", 10, 9, 12, 80)
    alerts, rows, still_open = review_positions("2026-09-25", data, manual, tracked, [buy], {})
    assert any(a.symbol == "UP" and a.kind == "STOP HIT" for a in alerts)
    assert [p.symbol for p in still_open] == ["NEW"]  # UP closed, NEW added
    assert rows[0][0].stop is not None  # trailing stop filled in
