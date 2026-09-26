"""Turn suggestions into a Markdown report and a short Telegram message."""
from datetime import date

DISCLAIMER = "Rule-based signals for education only. Not financial advice. Do your own research."


def _table(rows):
    if not rows:
        return "_No setups today._\n"
    lines = ["| Stock | Action | Entry | Stop | Target | R:R | Score | Why |",
             "|---|---|---|---|---|---|---|---|"]
    for s in rows:
        lines.append(f"| {s.symbol} | {s.action} | {s.entry} | {s.stop} | {s.target} | "
                     f"{s.risk_reward} | {s.score} | {'; '.join(s.reasons)} |")
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


def to_telegram(day: date, long_term, intraday, alerts=(), limit: int = 5) -> str:
    def line(s):
        return f"• {s.symbol} {s.action} {s.entry} | SL {s.stop} | T {s.target}"

    msg = [f"📊 Daily report {day:%d %b %Y}", ""]
    if alerts:
        msg += ["Alerts:"] + [a.text() for a in alerts] + [""]
    msg += ["Long-term:"]
    msg += [line(s) for s in long_term[:limit]] or ["• none"]
    msg += ["", "Intraday (next session):"]
    msg += [line(s) for s in intraday[:limit]] or ["• none"]
    msg += ["", DISCLAIMER]
    return "\n".join(msg)
