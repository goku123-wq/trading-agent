"""Turn suggestions into a Markdown report and a short Telegram message."""
from datetime import date

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
    lines = ["| Stock | Action | Entry | Stop | Target | R:R | Score | Qty | Capital | Loss at stop | Cap | Why |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for s in rows:
        z = s.sizing()
        qty, cap_needed, loss = (z[0], inr(z[1]), inr(z[2])) if z else ("-", "-", "-")
        lines.append(f"| {s.symbol} | {s.action} | {s.entry} | {s.stop} | {s.target} | "
                     f"{s.risk_reward} | {s.score} | {qty} | {cap_needed} | {loss} | {s.cap or '-'} | "
                     f"{'; '.join(s.reasons)} |")
    return "\n".join(lines) + "\n"


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
        "## Long-term buys\n", _table(buys),
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
    if (z := s.sizing()):
        out += f"\n   Qty {z[0]} ({inr(z[1])}), loss at SL {inr(z[2])}"
    if why and s.reasons:
        out += f"\n   {', '.join(s.reasons)}"
    return out


def sizing_note() -> str:
    from agent.signals import profit_goal
    return (f"Qty = shares to make ~{inr(profit_goal())} at target. Check the loss at SL fits your budget; "
            "intraday needs only the broker's margin, not the full capital.")


def to_telegram(day: date, long_term, intraday, alerts=(), limit: int = 5) -> str:
    msg = [f"📊 Daily report {day:%d %b %Y}", "[L] large cap, [M] mid cap, [W] your watchlist", ""]
    if alerts:
        msg += ["Alerts:"] + [a.text() for a in alerts] + [""]
    buys = [s for s in long_term if s.action == "BUY"]
    exits = [s for s in long_term if s.action != "BUY"]
    for title, cap in (("Long-term buys, large caps:", "Large"), ("Long-term buys, mid caps:", "Mid"),
                       ("Long-term buys, watchlist:", "Watch")):
        group = [s for s in buys if s.cap == cap]
        if group or cap != "Watch":
            msg += [title] + ([line(s) for s in group[:limit]] or ["• none"]) + [""]
    other = [s for s in buys if s.cap not in ("Large", "Mid", "Watch")]
    if other:
        msg += ["Long-term buys:"] + [line(s) for s in other[:limit]] + [""]
    if exits:
        msg += ["Exit / avoid:"] + [line(s) for s in exits[:limit]] + [""]
    msg += ["Intraday (next session):"]
    msg += [line(s) for s in intraday[:2 * limit]] or ["• none"]
    msg += ["", sizing_note(), DISCLAIMER]
    return "\n".join(msg)
