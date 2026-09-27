"""Size a basket of ideas so the combined profit at target is about PROFIT_GOAL rupees.

The goal is split equally across the picked stocks; each quantity is rounded up.
"""
import math
from dataclasses import dataclass
from typing import Optional

from agent.signals import Suggestion, profit_goal

import os


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name) or default)
    except ValueError:
        return default


def capital() -> float:
    """Rupees available per basket. Set CAPITAL (GitHub variable) to change."""
    return _env_float("CAPITAL", 50000)


def intraday_leverage() -> float:
    """Exposure allowed per rupee of capital for intraday (MIS).

    Default 1: the basket's total buy value stays within your amount. Groww gives up to ~5x margin on many
    stocks; set INTRADAY_LEVERAGE to use it.
    """
    return _env_float("INTRADAY_LEVERAGE", 1)


@dataclass
class Leg:
    s: Suggestion
    qty: int
    capital: float
    profit: float  # at target
    loss: float  # at stop-loss


@dataclass
class Basket:
    legs: list
    goal: float = 0.0
    budget: float = 0.0  # capital available (margin for intraday)
    leverage: float = 1.0

    @property
    def margin(self) -> float:
        return self.capital / self.leverage

    @property
    def short_of_goal(self) -> bool:
        return bool(self.legs) and self.profit < self.goal * 0.95

    @property
    def capital(self) -> float:
        return sum(x.capital for x in self.legs)

    @property
    def profit(self) -> float:
        return sum(x.profit for x in self.legs)

    @property
    def loss(self) -> float:
        return sum(x.loss for x in self.legs)


def pick(ideas: list[Suggestion], size: int = 5, mix: Optional[dict] = None) -> list[Suggestion]:
    """Top buy ideas by score; with `mix` (e.g. {"Large": 3, "Mid": 2}) take that many per cap first.

    Baskets are buy-only (BUY / BUY above): no short-selling.
    """
    # Best score first; among equals prefer bigger % moves so the goal needs less capital.
    ideas = sorted((s for s in ideas if s.action.startswith("BUY") and s.target != s.entry),
                   key=lambda s: (-s.score, -abs(s.target - s.entry) / s.entry))
    chosen = []
    for cap, n in (mix or {}).items():
        chosen += [s for s in ideas if s.cap == cap][:n]
    chosen += [s for s in ideas if s not in chosen][: size - len(chosen)]
    return chosen[:size]


def _leg(s: Suggestion, qty: int) -> Leg:
    move, risk = abs(s.target - s.entry), abs(s.entry - s.stop)
    return Leg(s, qty, round(qty * s.entry, 2), round(qty * move, 2), round(qty * risk, 2))


def make_basket(ideas: list[Suggestion], goal: Optional[float] = None, size: int = 5,
                mix: Optional[dict] = None, budget: Optional[float] = None, leverage: float = 1.0) -> Basket:
    """Size picks so the combined profit at target is `goal`, without exposure above budget x leverage.

    If the goal needs more than the budget allows, quantities are scaled down to fit and the basket
    reports the smaller profit it can make (short_of_goal).
    """
    goal = goal or profit_goal()
    budget = budget if budget is not None else capital()
    picks = pick(ideas, size, mix)
    if not picks:
        return Basket([], goal, budget, leverage)
    share = goal / len(picks)
    qtys = [math.ceil(share / abs(s.target - s.entry)) for s in picks]
    limit = budget * leverage
    exposure = sum(q * s.entry for q, s in zip(qtys, picks))
    if budget > 0 and exposure > limit:
        f = limit / exposure
        qtys = [math.floor(q * f) for q in qtys]
        # Rounding down leaves spare cash: top up one share at a time, best profit per rupee first.
        spare = limit - sum(q * s.entry for q, s in zip(qtys, picks))
        order = sorted(range(len(picks)), key=lambda i: -abs(picks[i].target - picks[i].entry) / picks[i].entry)
        profit = sum(q * abs(s.target - s.entry) for q, s in zip(qtys, picks))
        while profit < goal:
            i = next((i for i in order if picks[i].entry <= spare), None)
            if i is None:
                break
            qtys[i] += 1
            spare -= picks[i].entry
            profit += abs(picks[i].target - picks[i].entry)
    legs = [_leg(s, q) for s, q in zip(picks, qtys) if q > 0]
    return Basket(legs, goal, budget, leverage)
