"""Answer "how much, what profit" over Telegram with sized baskets from the latest ideas.

Reply formats understood (case-insensitive):
    50000 5000
    50k 5k
    capital 50000 profit 5000
    1.5L 10k long        (only the long-term basket)
    50000 5000 intraday  (only the intraday basket)
"""
import re
from typing import Optional

from agent.basket import intraday_leverage, make_basket
from agent.report import LONG_MIX, basket_lines, inr
from agent.signals import Suggestion

_NUM = re.compile(r"(\d+(?:\.\d+)?)\s*(k|l|lakh|lakhs|lac|cr|crore)?\b", re.I)
_MULT = {"k": 1e3, "l": 1e5, "lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "cr": 1e7, "crore": 1e7}


def parse_request(text: str) -> Optional[tuple[float, float, str]]:
    """(capital, profit goal, style) from a message, or None if it has no two amounts."""
    t = (text or "").replace(",", "").replace("₹", " ").lower()
    nums = [float(n) * _MULT.get((u or "").lower(), 1) for n, u in _NUM.findall(t)]
    if len(nums) < 2:
        return None
    capital, goal = nums[0], nums[1]
    if capital <= 0 or goal <= 0:
        return None
    if "intra" in t:
        style = "intraday"
    elif "long" in t or "delivery" in t:
        style = "long"
    else:
        style = "both"
    return capital, goal, style


def _ideas(rows: list[dict]) -> list[Suggestion]:
    return [Suggestion(r["symbol"], "", r["action"], r["entry"], r["stop"], r["target"], r["score"],
                       r.get("reasons", []), r.get("cap", "")) for r in rows]


def answer(ideas: dict, capital: float, goal: float, style: str = "both") -> str:
    daily = ideas.get("daily") or {}
    if not daily:
        return "No report yet, so I have no ideas to size. The evening report runs at 5 PM on trading days."
    out = [f"🧮 Plan for {inr(capital)} capital, {inr(goal)} profit goal",
           f"(from the {daily.get('day', '')} evening report)", ""]
    if style in ("both", "long"):
        b = make_basket(_ideas(daily.get("long_term", [])), goal=goal, budget=capital, mix=LONG_MIX)
        out += basket_lines("💼 Long-term: buy at market open, delivery (CNC)", b) + [""]
    if style in ("both", "intraday"):
        b = make_basket(_ideas(daily.get("intraday", [])), goal=goal, budget=capital, leverage=intraday_leverage())
        out += basket_lines("🎯 Intraday: enter only if the level breaks after 9:30, MIS", b) + [""]
    if style == "both":
        out.append("Each basket uses most of your capital: pick one, not both.")
    out.append("Reply with new numbers anytime before 9:30 to re-plan. Not financial advice.")
    return "\n".join(out)


ASK = ("☀️ Good morning! How much do you want to trade today, and what profit are you aiming for?\n\n"
       "Reply with two numbers: capital then profit, e.g. 50000 5000 (or 50k 5k).\n"
       "Add 'long' or 'intraday' to get just one basket. I reply within seconds, any time.")

HELP = ("I didn't catch two amounts. Reply like: 50000 5000 (capital, then profit goal). "
        "You can also write 50k 5k or 1.5L 10k long.")
