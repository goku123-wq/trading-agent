from agent.planner import ASK, HELP, answer, parse_request
from run_planner import handle


def idea(sym, cap, entry=100, stop=95, target=110, action="BUY", score=80):
    return {"symbol": sym, "action": action, "entry": entry, "stop": stop, "target": target, "score": score,
            "cap": cap, "reasons": ["r"]}


IDEAS = {"daily": {"day": "2026-09-25",
                   "long_term": [idea("L1", "Large"), idea("L2", "Large"), idea("L3", "Large"), idea("M1", "Mid"),
                                 idea("M2", "Mid")],
                   "intraday": [idea("I1", "Large", 100, 102, 97, "SELL below", 70)]}}


def test_parse_request():
    assert parse_request("50000 5000") == (50000, 5000, "both")
    assert parse_request("50k 5k") == (50000, 5000, "both")
    assert parse_request("capital ₹50,000 profit ₹5,000") == (50000, 5000, "both")
    assert parse_request("1.5L 10k long") == (150000, 10000, "long")
    assert parse_request("50000 5000 intraday") == (50000, 5000, "intraday")
    assert parse_request("hello") is None
    assert parse_request("50000") is None


def test_answer_both_baskets():
    txt = answer(IDEAS, 50000, 5000)
    assert "Plan for ₹50.0k capital, ₹5.0k profit goal" in txt
    assert "Long-term" in txt and "L1" in txt and "M2" in txt
    assert "Intraday" in txt and "I1" in txt and "pick one" in txt


def test_answer_one_style_and_no_report():
    assert "Intraday" not in answer(IDEAS, 50000, 5000, "long")
    assert "No report yet" in answer({}, 50000, 5000)


def test_handle_ignores_strangers_and_helps():
    ups = [{"update_id": 1, "message": {"chat": {"id": 42}, "text": "50000 5000"}},
           {"update_id": 2, "message": {"chat": {"id": 999}, "text": "50000 5000"}},
           {"update_id": 3, "message": {"chat": {"id": 42}, "text": "what?"}},
           {"update_id": 4, "message": {"chat": {"id": 42}, "text": "/start"}}]
    out = handle(ups, "42", IDEAS)
    assert len(out) == 3 and "Plan for" in out[0] and out[1] == HELP and out[2] == ASK
