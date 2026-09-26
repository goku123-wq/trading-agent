import numpy as np
import pandas as pd

from agent import morning
from agent.indicators import add_indicators
from agent.signals import Suggestion
from run_morning import load_previous_intraday
from tests.test_signals import make_df


def bars(prices, start="2026-09-28 09:15", vol=1000):
    idx = pd.date_range(start, periods=len(prices), freq="5min", tz="Asia/Kolkata")
    p = np.asarray(prices, dtype=float)
    return pd.DataFrame({"Open": p, "High": p * 1.001, "Low": p * 0.999, "Close": p,
                         "Volume": np.full(len(p), vol, dtype=float)}, index=idx)


def daily_up():
    return add_indicators(make_df(np.linspace(100, 200, 250)))  # last close 200


def daily_down():
    return add_indicators(make_df(np.linspace(300, 200, 250)))  # last close 200


def test_mood():
    up = morning.IndexMove("NIFTY 50", 25000, 0.8, 0.4)
    down = morning.IndexMove("NIFTY 50", 25000, -0.9, -0.3)
    vix_spike = morning.IndexMove("INDIA VIX", 15, 8, 5)
    assert morning.mood(up, None, 40, 10) == "Bullish"
    assert morning.mood(down, vix_spike, 10, 40) == "Bearish"
    assert morning.mood(up, vix_spike, 20, 20) == "Mixed"


def test_orb_buy_after_range_breakout():
    # 9:15-10:00 range 200-201, then pushes to 201.8 by 10:05
    b = bars([200.2, 200.5, 200.1, 200.8, 200.4, 200.9, 200.3, 200.7, 200.6, 201.0, 200.8, 200.9, 201.8])
    s = morning.opening_range_setup("X", b, daily_up(), "Bullish")
    assert s is not None and s.action == "BUY"
    assert s.stop < s.entry < s.target
    assert s.score == 80


def test_orb_sell_in_downtrend_and_blocked_when_market_bullish():
    b = bars([200.2, 199.8, 200.1, 199.9, 200.0, 199.7, 200.1, 199.9, 199.8, 200.0, 199.9, 199.8, 198.9])
    s = morning.opening_range_setup("X", b, daily_down(), "Mixed")
    assert s is not None and s.action == "SELL" and s.target < s.entry < s.stop
    assert morning.opening_range_setup("X", b, daily_down(), "Bullish") is None


def test_orb_none_inside_range_or_against_trend():
    inside = bars([200.2, 200.5, 200.1, 200.8, 200.4, 200.9, 200.3, 200.7, 200.6, 200.5])
    assert morning.opening_range_setup("X", inside, daily_up()) is None
    up_break = bars([200.2, 200.5, 200.1, 200.8, 200.4, 200.9, 200.3, 200.7, 200.6, 200.9, 201.8])
    assert morning.opening_range_setup("X", up_break, daily_down()) is None


def test_triggered():
    b = bars([100, 101, 102])
    assert morning.triggered(Suggestion("X", "intraday", "BUY above", 102.05, 99, 105, 0), b)
    assert not morning.triggered(Suggestion("X", "intraday", "BUY above", 103, 99, 105, 0), b)
    assert morning.triggered(Suggestion("X", "intraday", "SELL below", 100, 101, 98, 0), b)


def test_load_previous_intraday(tmp_path):
    p = tmp_path / "latest.md"
    p.write_text("## Long-term buys\n| TITAN | BUY | 1 | 0.5 | 2 | 2.0 | 80 | x |\n"
                 "## Intraday watchlist for next session\n"
                 "| ADANIENT | SELL below | 2895.27 | 2939.9 | 2828.34 | 1.5 | 70 | x |\n"
                 "| DRREDDY | BUY above | 1209.96 | 1193.4 | 1234.8 | 1.5 | 50 | y |\n")
    got = load_previous_intraday(p)
    assert [(s.symbol, s.action, s.entry) for s in got] == [("ADANIENT", "SELL below", 2895.27),
                                                            ("DRREDDY", "BUY above", 1209.96)]


def test_telegram_text():
    s = Suggestion("X", "10am", "BUY", 201.8, 200.9, 203.15, 80, ["broke above 9:15-10:00 high"])
    msg = morning.to_telegram(pd.Timestamp("2026-09-28").date(), "Bullish",
                              morning.IndexMove("NIFTY 50", 25100, 0.5, 0.2), None, None, 30, 20, [s], [])
    assert "Mood: Bullish" in msg and "X BUY 201.8" in msg and "Not financial advice" in msg


def test_telegram_groups_by_cap():
    a = Suggestion("BIG", "10am", "BUY", 1, 0.9, 1.15, 80, ["r"], cap="Large")
    b = Suggestion("MIDDY", "10am", "SELL", 1, 1.1, 0.85, 70, ["r"], cap="Mid")
    msg = morning.to_telegram(pd.Timestamp("2026-09-28").date(), "Mixed", None, None, None, 1, 1, [a, b], [])
    assert "Basket now: ~" in msg and "[L] BIG" in msg and "[M] MIDDY" in msg and "Qty" in msg
