"""Turn suggestions into a Markdown report and a short Telegram message."""
from datetime import date

from agent.basket import intraday_leverage, make_basket

LONG_MIX = {"Large": 3, "Mid": 2}  # long-term basket: 3 large caps + 2 mid caps

DISCLAIMER = "Rule-based signals for education only. Not financial advice. Do your own research."


def inr(x: float) -> str:
    """Short rupee format: ₹950, ₹12.5k, ₹1.2L, ₹2.1Cr."""
    if x >= 1e7:
        return f"₹{x / 1e7:.1f}Cr"
    if x >= 1e5:
        return f"₹{x / 1e5:.1f}L"
    if x >= 1e3:
        return f"₹{x / 1e3:.1f}k"
    return f"₹{x:.0f}"


def _table(rows):
    if not rows:
        return "_No setups today._\n"
    lines = ["| Stock | Action | Entry | Stop | Target | R:R | Score | Cap | Why |",
             "|---|---|---|---|---|---|---|---|---|"]
    for s in rows:
        lines.append(f"| {s.symbol} | {s.action} | {s.entry} | {s.stop} | {s.target} | "
                     f"{s.risk_reward} | {s.score} | {s.cap or '-'} | {'; '.join(s.reasons)} |")
    return "\n".join(lines) + "\n"


def _basket_table(b) -> str:
    if not b.legs:
        return "_No ideas today._\n"
    lines = ["| Stock | Action | Entry | Stop | Target | Qty | Capital | Profit at target | Loss at stop | Cap |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for x in b.legs:
        s = x.s
        lines.append(f"| {s.symbol} | {s.action} | {s.entry} | {s.stop} | {s.target} | {x.qty} | "
                     f"{inr(x.capital)} | {inr(x.profit)} | {inr(x.loss)} | {s.cap or '-'} |")
    lines.append(f"| **Total** | | | | | | **{inr(b.capital)}** | **{inr(b.profit)}** | **{inr(b.loss)}** | |")
    return "\n".join(lines) + "\n\n" + _basket_summary(b) + "\n"


def _basket_summary(b) -> str:
    if b.leverage > 1:
        used = f"{inr(b.margin)} margin of your {inr(b.budget)} (exposure {inr(b.capital)} at ~{b.leverage:g}x)"
    else:
        used = f"{inr(b.capital)} of your {inr(b.budget)}"
    out = f"Uses {used} | +{inr(b.profit)} at targets | -{inr(b.loss)} if all stops hit"
    if b.short_of_goal:
        out += f"\n⚠️ {inr(b.goal)} needs more capital than {inr(b.budget)} on these picks; sized down to fit."
    return out


def _alerts(alerts):
    return "\n".join(f"- {a.text()}" for a in alerts) + "\n" if alerts else "_None today._\n"


def _positions(rows):
    if not rows:
        return "_No positions listed. Add them to config/positions.csv._\n"
    lines = ["| Stock | Entry | Stop | Target | Last close | P&L % |", "|---|---|---|---|---|---|"]
    for p, last in rows:
        pnl = (last / p.entry - 1) * 100 * (1 if p.side == "LONG" else -1) if p.entry else 0
        lines.append(f"| {p.symbol} | {p.entry} | {p.stop} | {p.target or '-'} | {last:.2f} | {pnl:+.1f} |")
    return "\n".join(lines) + "\n"


def to_markdown(day: date, long_term, intraday, skipped, alerts=(), positions=()) -> str:
    buys = [s for s in long_term if s.action == "BUY"]
    exits = [s for s in long_term if s.action != "BUY"]
    parts = [
        f"# Daily trade report, {day:%d %b %Y}\n",
        f"> {DISCLAIMER}\n",
        f"> {sizing_note()}\n",
        "## Stop-loss / target alerts\n", _alerts(alerts),
        "## Your positions\n", _positions(positions),
        "## Long-term basket\n", _basket_table(make_basket(buys, mix=LONG_MIX)),
        "## Intraday basket for next session\n", _basket_table(make_basket(intraday, leverage=intraday_leverage())),
        "## All long-term buys\n", _table(buys),
        "## Long-term exits / avoid\n", _table(exits),
        "## Intraday watchlist for next session\n",
        "Trigger only if price crosses the entry level after 9:30 AM. Square off by 3:15 PM.\n\n",
        _table(intraday),
    ]
    if skipped:
        parts.append(f"\n_No data for: {', '.join(skipped)}_\n")
    return "\n".join(parts)


def line(s, why: bool = False) -> str:
    tag = f"[{s.cap[0]}] " if s.cap else ""
    out = f"• {tag}{s.symbol} {s.action} {s.entry} | SL {s.stop} | T {s.target}"
    if why and s.reasons:
        out += f"\n   {', '.join(s.reasons)}"
    return out


def basket_lines(title: str, b, why: bool = False) -> list[str]:
    if not b.legs:
        return [title, "• none"]
    out = [f"{title}: ~{inr(b.profit)} if all hit target"]
    for x in b.legs:
        out.append(line(x.s, why) + f"\n   Qty {x.qty} ({inr(x.capital)})")
    out.append(_basket_summary(b))
    return out


def sizing_note() -> str:
    from agent.signals import profit_goal
    from agent.basket import capital
    return (f"Baskets aim for ~{inr(profit_goal())} combined at target using up to {inr(capital())}. "
            "Intraday uses broker margin (MIS); square off by 3:15 PM.")


def to_telegram(day: date, long_term, intraday, alerts=(), limit: int = 8) -> str:
    msg = [f"📊 Daily report {day:%d %b %Y}", "[L] large cap, [M] mid cap, [W] your watchlist", ""]
    if alerts:
        msg += ["Alerts:"] + [a.text() for a in alerts] + [""]
    buys = [s for s in long_term if s.action == "BUY"]
    exits = [s for s in long_term if s.action != "BUY"]
    lt = make_basket(buys, mix=LONG_MIX)
    msg += basket_lines("💼 Long-term basket", lt) + [""]
    more = [s for s in buys if s not in [x.s for x in lt.legs]]
    if more:
        msg += ["More long-term ideas: " + ", ".join(f"{s.symbol} [{s.cap[:1] or '-'}]" for s in more[:limit]), ""]
    if exits:
        msg += ["Exit / avoid:"] + [line(s) for s in exits[:limit]] + [""]
    msg += basket_lines("🎯 Intraday basket (next session)", make_basket(intraday, leverage=intraday_leverage()))
    msg += ["", sizing_note(), DISCLAIMER]
    return "\n".join(msg)
