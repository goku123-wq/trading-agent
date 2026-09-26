"""Size a basket of ideas so the combined profit at target is about PROFIT_GOAL rupees.

The goal is split equally across the picked stocks; each quantity is rounded up.
"""
import math
from dataclasses import dataclass
from typing import Optional

from agent.signals import Suggestion, profit_goal


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
    """Top ideas by score; with `mix` (e.g. {"Large": 3, "Mid": 2}) take that many per cap first."""
    ideas = sorted((s for s in ideas if s.action != "SELL/EXIT" and s.target != s.entry), key=lambda s: -s.score)
    chosen = []
    for cap, n in (mix or {}).items():
        chosen += [s for s in ideas if s.cap == cap][:n]
    chosen += [s for s in ideas if s not in chosen][: size - len(chosen)]
    return sorted(chosen[:size], key=lambda s: -s.score)


def make_basket(ideas: list[Suggestion], goal: Optional[float] = None, size: int = 5,
                mix: Optional[dict] = None) -> Basket:
    picks = pick(ideas, size, mix)
    if not picks:
        return Basket([])
    share = (goal or profit_goal()) / len(picks)
    legs = []
    for s in picks:
        move, risk = abs(s.target - s.entry), abs(s.entry - s.stop)
        qty = math.ceil(share / move)
        legs.append(Leg(s, qty, round(qty * s.entry, 2), round(qty * move, 2), round(qty * risk, 2)))
    return Basket(legs)
