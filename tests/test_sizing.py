from agent.report import inr, line
from agent.signals import Suggestion


def test_quantity_hits_profit_goal():
    s = Suggestion("X", "long-term", "BUY", 165.71, 158.10, 180.92, 90)
    qty, capital, loss = s.sizing(10000)
    assert qty == 658  # ceil(10000 / 15.21)
    assert qty * (s.target - s.entry) >= 10000 > (qty - 1) * (s.target - s.entry)
    assert capital == round(658 * 165.71, 2)
    assert loss == round(658 * (165.71 - 158.10), 2)


def test_short_and_exit():
    short = Suggestion("X", "intraday", "SELL below", 100, 102, 97, 50)
    assert short.sizing(10000)[0] == 3334
    assert Suggestion("X", "long-term", "SELL/EXIT", 100, 105, 90, 80).sizing(10000) is None


def test_profit_goal_env(monkeypatch):
    monkeypatch.setenv("PROFIT_GOAL", "5000")
    assert Suggestion("X", "long-term", "BUY", 100, 95, 110, 80).sizing()[0] == 500
    monkeypatch.setenv("PROFIT_GOAL", "")
    assert Suggestion("X", "long-term", "BUY", 100, 95, 110, 80).sizing()[0] == 1000


def test_inr_and_line():
    assert [inr(950), inr(12500), inr(125000), inr(21000000)] == ["₹950", "₹12.5k", "₹1.2L", "₹2.1Cr"]
    txt = line(Suggestion("X", "long-term", "BUY", 100, 95, 110, 80, cap="Large"))
    assert "[L] X BUY 100" in txt and "Qty 1000 (₹1.0L), loss at SL ₹5.0k" in txt
