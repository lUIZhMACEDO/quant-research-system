"""End-to-end render of the full dashboard (all five tabs) with every data provider stubbed out."""

import datetime as dt
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from conftest import make_ohlcv

APP = str(Path(__file__).resolve().parents[1] / "app.py")

TECH = {
    "rsi": 48.0,
    "rsi_label": "NEUTRAL",
    "macd_label": "NEUTRAL",
    "bb_label": "MID RANGE",
    "ema_label": "GOLDEN CROSS",
    "vol_label": "NORMAL",
    "atr_stop": 95.0,
    "atr_target": 110.0,
}


def _holding(tk):
    return {
        "ticker": tk,
        "name": f"{tk} <Inc>",
        "shares": 5,
        "avg_cost": 100.0,
        "current_price": 105.0,
        "prev_close": 104.0,
        "total_cost": 500.0,
        "market_value": 525.0,
        "open_pnl": 25.0,
        "open_pnl_pct": 5.0,
        "day_pnl": 5.0,
        "day_pnl_pct": 0.96,
        "pe": 22.0,
        "market_cap": "$1.00B",
        "hi52": 120.0,
        "lo52": 80.0,
        "range_pct": 62.5,
        "signal": "HOLD",
        "reason": "Long-term compounding",
        "action": "Thesis intact.",
        "strategy_note": "<script>x</script>",
        "strategy": "",
        "tech": TECH,
        "fins": {"beta": 1.0, "sector": "Technology"},
        "earn": {"days_to_earnings": 12, "next_earnings": dt.date(2026, 11, 28)},
        "analyst": {
            "rec_buy": 3,
            "rec_hold": 1,
            "rec_sell": 0,
            "target_mean": 120.0,
            "target_low": 100.0,
            "target_high": 140.0,
            "insider_buys": 0,
            "insider_sells": 1,
        },
        "news": {"headlines": [], "sentiment_score": 0.0},
        "timeline": {
            "short_level": "s",
            "short_trigger": "t",
            "med_catalyst": "m",
            "med_target": "mt",
            "long_thesis": "l",
            "long_invalidate": "li",
        },
    }


PICK = {
    "ticker": "AMD",
    "name": "Advanced Micro Devices",
    "current_price": 100.0,
    "day_chg": -1.0,
    "status": "ACTIVE",
    "strategy_name": "RSI Momentum + MACD Cross",
    "reason": "test",
    "entry": 99.2,
    "target": 108.0,
    "stop": 96.2,
    "rr": 2.9,
    "pos_size": 33,
    "risk_pct": 3.0,
    "reward_pct": 8.9,
    "fill_window": "Limit in range",
    "tech": TECH,
}
RISK = {
    "weighted_beta": 1.0,
    "risk_rating": "MEDIUM",
    "var_95": 12.0,
    "sectors": {"Technology": 100.0},
    "positions": [{"ticker": "VOO", "weight": 100.0, "beta": 1.0, "risk_1d": 10.5}],
}
MACRO = {
    "headlines": [{"title": "Markets <b>rally</b>", "link": "javascript:alert(1)", "publisher": "Wire"}],
    "risks": [{"ticker": "VOO", "level": "MEDIUM", "reason": "Fed", "keyword": "fed"}],
}


@pytest.fixture
def stubbed(monkeypatch):
    from quant_research.config import reset_settings
    from quant_research.dashboard import app as dash
    from quant_research.dashboard import charts

    monkeypatch.setenv("APP_PASSWORD", "pw")
    monkeypatch.setenv("PUBLIC_MODE", "0")  # owner mode: renders the dashboard straight away
    for key in ("SENDER_EMAIL", "EMAIL_PASSWORD"):
        monkeypatch.delenv(key, raising=False)
    reset_settings()

    hist = make_ohlcv(np.linspace(100, 110, 60), capitalised=True)
    monkeypatch.setattr(
        dash, "load_market", lambda: {"price": 6000.0, "change": 0.4, "spy_rsi": 52, "spy_mood": "Neutral"}
    )
    monkeypatch.setattr(dash, "load_picks", lambda: ([PICK], [PICK]))
    monkeypatch.setattr(dash, "load_news", lambda tickers: (MACRO, []))
    monkeypatch.setattr(dash, "analyse_user_portfolio", lambda pf: [_holding(p["ticker"]) for p in pf])
    monkeypatch.setattr(dash, "compute_risk_dashboard", lambda h: RISK)
    monkeypatch.setattr(
        dash, "get_live_prices", lambda t: {tk: {"price": 106.0, "change": 1.0, "change_pct": 0.95} for tk in t}
    )
    monkeypatch.setattr(dash, "get_fear_greed", lambda: {"value": 62, "label": "Greed"})
    monkeypatch.setattr(
        dash, "get_crypto_prices", lambda: {"bitcoin": {"usd": 90000, "usd_24h_change": 1.2, "usd_market_cap": 1.8e12}}
    )
    monkeypatch.setattr(dash, "compute_technicals", lambda tk: TECH)
    monkeypatch.setattr(charts, "get_hist", lambda *a, **k: hist)
    yield
    reset_settings()


def test_full_dashboard_renders(stubbed):
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.text_input(key="pwd_gate").input("pw")
    at.button[0].click().run()

    assert not at.exception, at.exception
    assert at.session_state["page_mode"] == "personal"
    assert len(at.tabs) == 5
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Risk Rating"] == "MEDIUM"
    assert metrics["Fear & Greed Index"] == "62 — Greed"
    html = "".join(m.value for m in at.markdown)
    assert "<script>x</script>" not in html and "&lt;script&gt;x&lt;/script&gt;" in html
    assert "javascript:" not in html
    assert "VOO" in html
    frames = [df.value for df in at.dataframe]
    assert any(isinstance(f, pd.DataFrame) and "ATR Stop" in f.columns for f in frames)
