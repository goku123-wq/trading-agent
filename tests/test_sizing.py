from agent.basket import make_basket, pick
from agent.report import basket_lines, inr
from agent.signals import Suggestion


def S(sym, score, cap="Large", entry=100, stop=95, target=110, action="BUY"):
    return Suggestion(sym, "long-term", action, entry, stop, target, score, cap=cap)


def test_basket_total_profit_is_goal():
    ideas = [S("A", 90, entry=165.71, stop=158.10, target=180.92), S("B", 80, entry=418.95, stop=395.24, target=466.37),
             S("C", 70)]
    b = make_basket(ideas, goal=5000, size=5, budget=10**9)
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


def test_buy_only_and_empty():
    short = Suggestion("S", "intraday", "SELL below", 100, 102, 97, 90)
    buy = Suggestion("X", "intraday", "BUY above", 100, 98, 103, 50)
    b = make_basket([short, buy], goal=5000, budget=10**9)
    assert [leg.s.symbol for leg in b.legs] == ["X"]  # no short-selling
    assert b.legs[0].qty == 1667 and b.loss == 3334
    assert make_basket([], goal=5000).legs == []


def test_profit_goal_env(monkeypatch):
    monkeypatch.setenv("PROFIT_GOAL", "")
    assert make_basket([S("A", 90)], budget=10**9).legs[0].qty == 500  # default 5000 / 10
    monkeypatch.setenv("PROFIT_GOAL", "2000")
    assert make_basket([S("A", 90)], budget=10**9).legs[0].qty == 200


def test_inr_and_lines():
    assert [inr(950), inr(12500), inr(125000), inr(21000000)] == ["₹950", "₹12.5k", "₹1.2L", "₹2.1Cr"]
    txt = "\n".join(basket_lines("Basket", make_basket([S("A", 90), S("B", 80, "Mid")], goal=5000, budget=50000)))
    assert "Basket: ~₹5.0k if all hit target" in txt and "[L] A BUY 100" in txt and "Qty 250 (₹25.0k)" in txt
    assert "Uses ₹50.0k of your ₹50.0k | +₹5.0k at targets | -₹2.5k if all stops hit" in txt
    assert "⚠️" not in txt


def test_capital_cap_scales_down_and_warns():
    ideas = [S("A", 90), S("B", 80)]  # 10% targets: Rs 5k needs Rs 50k
    b = make_basket(ideas, goal=5000, budget=30000)
    assert b.capital <= 30000 and b.short_of_goal
    assert [x.qty for x in b.legs] == [150, 150] and b.profit == 3000
    txt = "\n".join(basket_lines("Basket", b))
    assert "⚠️ ₹5.0k needs more capital than ₹30.0k" in txt


def test_intraday_leverage_uses_margin():
    buy = Suggestion("X", "intraday", "BUY above", 100, 98, 103, 50)  # 3% move: Rs 5k needs 1.67L exposure
    b = make_basket([buy], goal=5000, budget=50000, leverage=5)
    assert b.legs[0].qty == 1667 and not b.short_of_goal
    assert round(b.margin) == 33340
    assert "margin of your ₹50.0k" in "\n".join(basket_lines("B", b))
    assert make_basket([buy], goal=5000, budget=50000, leverage=1).short_of_goal


def test_capital_env(monkeypatch):
    monkeypatch.setenv("CAPITAL", "20000")
    assert make_basket([S("A", 90)], goal=5000).capital <= 20000


def test_top_up_uses_spare_capital():
    # expensive shares: floor-scaling alone would leave lots of cash idle
    ideas = [S("BIG", 90, entry=4988.5, stop=4785.67, target=5394.17), S("CHEAP", 80, entry=165.71, stop=158.1, target=180.92)]
    b = make_basket(ideas, goal=5000, budget=30000)
    assert b.capital <= 30000
    assert 30000 - b.capital < 4988.5  # nothing affordable left over but less than one BIG share
    assert b.profit > 2500
