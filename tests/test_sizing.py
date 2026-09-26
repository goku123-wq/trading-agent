from agent.basket import make_basket, pick
from agent.report import basket_lines, inr
from agent.signals import Suggestion


def S(sym, score, cap="Large", entry=100, stop=95, target=110, action="BUY"):
    return Suggestion(sym, "long-term", action, entry, stop, target, score, cap=cap)


def test_basket_total_profit_is_goal():
    ideas = [S("A", 90, entry=165.71, stop=158.10, target=180.92), S("B", 80, entry=418.95, stop=395.24, target=466.37),
             S("C", 70)]
    b = make_basket(ideas, goal=5000, size=5)
    assert [x.s.symbol for x in b.legs] == ["A", "B", "C"]
    assert 5000 <= b.profit < 5000 + sum(abs(x.s.target - x.s.entry) for x in b.legs)
    for x in b.legs:  # each leg makes about a third
        assert x.profit >= 5000 / 3
        assert x.loss == round(x.qty * abs(x.s.entry - x.s.stop), 2)
    assert b.capital == sum(x.qty * x.s.entry for x in b.legs)


def test_pick_mix_and_skips_exits():
    ideas = [S("L1", 90), S("L2", 85), S("L3", 80), S("L4", 75), S("M1", 60, "Mid"), S("M2", 55, "Mid"),
             S("M3", 50, "Mid"), S("X", 99, action="SELL/EXIT")]
    got = [s.symbol for s in pick(ideas, 5, {"Large": 3, "Mid": 2})]
    assert got == ["L1", "L2", "L3", "M1", "M2"]
    # not enough mid caps: fill with the next best large caps
    got = [s.symbol for s in pick(ideas[:4] + [ideas[4]], 5, {"Large": 3, "Mid": 2})]
    assert sorted(got) == ["L1", "L2", "L3", "L4", "M1"]


def test_short_leg_and_empty():
    short = Suggestion("X", "intraday", "SELL below", 100, 102, 97, 50)
    b = make_basket([short], goal=5000)
    assert b.legs[0].qty == 1667 and b.loss == 3334
    assert make_basket([], goal=5000).legs == []


def test_profit_goal_env(monkeypatch):
    monkeypatch.setenv("PROFIT_GOAL", "")
    assert make_basket([S("A", 90)]).legs[0].qty == 500  # default 5000 / 10
    monkeypatch.setenv("PROFIT_GOAL", "2000")
    assert make_basket([S("A", 90)]).legs[0].qty == 200


def test_inr_and_lines():
    assert [inr(950), inr(12500), inr(125000), inr(21000000)] == ["₹950", "₹12.5k", "₹1.2L", "₹2.1Cr"]
    txt = "\n".join(basket_lines("Basket", make_basket([S("A", 90), S("B", 80, "Mid")], goal=5000)))
    assert "(~₹5.0k if all hit target)" in txt and "[L] A BUY 100" in txt and "Qty 250 (₹25.0k)" in txt
    assert "Total: ₹50.0k needed | +₹5.0k at targets | -₹2.5k if all stops hit" in txt
