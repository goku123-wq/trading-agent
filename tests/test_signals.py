import numpy as np
import pandas as pd

from agent.indicators import add_indicators, rsi
from agent.signals import intraday_setup, long_term_signal
from agent.report import to_markdown, to_telegram
from run_daily import build


def make_df(closes, vol=1_000_000, spread=0.01):
    closes = np.asarray(closes, dtype=float)
    idx = pd.bdate_range("2024-01-01", periods=len(closes))
    return pd.DataFrame({
        "Open": closes * (1 - spread / 4), "High": closes * (1 + spread),
        "Low": closes * (1 - spread), "Close": closes,
        "Volume": np.full(len(closes), vol, dtype=float),
    }, index=idx)


def uptrend_with_pullback():
    up = np.linspace(100, 200, 240)
    pull = np.linspace(200, 194, 6)
    bounce = [195.5]
    return make_df(np.concatenate([up, pull, bounce]))


def test_rsi_bounds():
    s = pd.Series(np.linspace(1, 100, 50))
    assert rsi(s).iloc[-1] == 100
    assert 0 <= rsi(pd.Series(np.random.default_rng(0).normal(100, 1, 300))).min() <= 100


def test_long_term_buy_on_pullback_in_uptrend():
    df = add_indicators(uptrend_with_pullback())
    s = long_term_signal("TEST", df)
    assert s is not None and s.action == "BUY"
    assert s.stop < s.entry < s.target
    assert s.risk_reward == 2.0


def test_long_term_exit_when_breaking_200dma():
    closes = np.concatenate([np.linspace(100, 150, 219), [120]])
    df = add_indicators(make_df(closes))
    s = long_term_signal("TEST", df)
    assert s is not None and s.action == "SELL/EXIT"


def test_no_signal_in_downtrend():
    df = add_indicators(make_df(np.linspace(200, 100, 250)))
    assert long_term_signal("TEST", df) is None


def test_too_little_history():
    df = add_indicators(make_df(np.linspace(100, 110, 50)))
    assert long_term_signal("TEST", df) is None
    assert intraday_setup("TEST", df) is None


def test_intraday_breakout_after_nr7_in_uptrend():
    df = make_df(np.linspace(100, 200, 250), spread=0.02)
    df.iloc[-1, df.columns.get_loc("High")] = df["Close"].iloc[-1] * 1.002
    df.iloc[-1, df.columns.get_loc("Low")] = df["Close"].iloc[-1] * 0.998
    s = intraday_setup("TEST", add_indicators(df))
    assert s is not None and s.action == "BUY above"
    assert s.stop < s.entry < s.target
    assert any("NR7" in r for r in s.reasons)


def test_intraday_breakdown_in_downtrend():
    df = make_df(np.linspace(200, 100, 250), spread=0.02)
    df.iloc[-1, df.columns.get_loc("Volume")] = 3_000_000
    s = intraday_setup("TEST", add_indicators(df))
    assert s is not None and s.action == "SELL below"
    assert s.target < s.entry < s.stop


def test_build_and_report():
    data = {"UP": add_indicators(uptrend_with_pullback()), "DOWN": add_indicators(make_df(np.linspace(200, 100, 250)))}
    lt, intra = build(data)
    md = to_markdown(pd.Timestamp("2026-09-25").date(), lt, intra, ["MISSING"])
    assert "UP" in md and "Not financial advice" in md and "MISSING" in md
    assert "UP BUY" in to_telegram(pd.Timestamp("2026-09-25").date(), lt, intra)
