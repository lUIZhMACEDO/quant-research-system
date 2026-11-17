"""Screens, composite scoring, trade plans, risk, proxies and valuation helpers."""

import datetime as dt

import numpy as np
import pytest

from quant_research.signals import screens
from quant_research.signals.proxies import build_space_economy_index, compute_proxy_scores
from quant_research.signals.risk import historical_var, portfolio_risk, risk_rating
from quant_research.signals.scoring import compute_signal_score, score_to_signal, signal_logic
from quant_research.signals.trade_plan import (
    compute_position_size,
    compute_trade_levels,
    fill_guidance,
    holding_action,
    holding_timeline,
    pick_status,
)
from quant_research.signals.valuation import (
    altman_label,
    altman_z,
    earnings_surprise_pct,
    estimate_revision_label,
    format_market_cap,
    peg_label,
    peg_ratio,
)

NEUTRAL_TECH = {
    "rsi": 50,
    "macd_label": "NEUTRAL",
    "bb_label": "MID RANGE",
    "ema_label": "N/A",
    "vol_label": "NORMAL",
    "vol_up_day": True,
}

# ---------------------------------------------------------------- screens


@pytest.mark.parametrize(
    "tech,expected",
    [
        ({"rsi": 40, "macd_label": "BULLISH CROSS"}, True),
        ({"rsi": 45, "macd_label": "BULLISH CROSS"}, False),
        ({"rsi": 30, "macd_label": "NEUTRAL"}, False),
        ({"rsi": None, "macd_label": "BULLISH CROSS"}, False),
    ],
)
def test_rsi_macd(tech, expected):
    assert screens.strategy_rsi_macd(tech) is expected


def test_bb_mean_reversion():
    assert screens.strategy_bb_mean_reversion({"bb_label": "NEAR LOWER", "rsi": 35})
    assert not screens.strategy_bb_mean_reversion({"bb_label": "NEAR LOWER", "rsi": 40})
    assert not screens.strategy_bb_mean_reversion({"bb_label": "MID RANGE", "rsi": 20})


def test_golden_cross_needs_volume():
    assert screens.strategy_golden_cross({"ema_label": "GOLDEN CROSS", "vol_label": "HIGH VOLUME"})
    assert not screens.strategy_golden_cross({"ema_label": "GOLDEN CROSS", "vol_label": "NORMAL"})


def test_earnings_rebound():
    assert screens.strategy_earnings_rebound({"rsi": 30}, 3)
    assert not screens.strategy_earnings_rebound({"rsi": 30}, 6)
    assert not screens.strategy_earnings_rebound({"rsi": 30}, None)


def test_detect_strategy_priority_order():
    tech = {"rsi": 30, "macd_label": "BULLISH CROSS", "bb_label": "NEAR LOWER"}
    assert screens.detect_strategy(tech, {}, {}) == "RSI_MACD"  # beats BB mean reversion
    assert screens.detect_strategy({"rsi": 30, "bb_label": "NEAR LOWER"}, {}, {}) == "BB_MEAN_REVERSION"
    assert screens.detect_strategy(NEUTRAL_TECH, {"insider_buys": 2}, {}) == "INSTITUTIONAL"
    assert screens.detect_strategy(NEUTRAL_TECH, {}, {}) == "MANUAL"
    assert set(screens.STRATEGY_NAMES) >= {
        "RSI_MACD",
        "BB_MEAN_REVERSION",
        "GOLDEN_CROSS",
        "EARNINGS_REBOUND",
        "INSTITUTIONAL",
        "MANUAL",
    }


# ---------------------------------------------------------------- scoring


def test_neutral_inputs_score_zero_hold():
    out = compute_signal_score("AAPL", NEUTRAL_TECH, {"trail_pe": 20}, {}, {"sentiment_score": 0.0})
    assert out["score"] == 0.0 and out["signal"] == "HOLD"
    assert out["reasoning"] == "No strong signals detected."


def test_bullish_components_add_up():
    tech = {
        "rsi": 25,
        "macd_label": "BULLISH CROSS",
        "bb_label": "NEAR LOWER",
        "ema_label": "GOLDEN CROSS",
        "vol_label": "HIGH VOLUME",
        "vol_up_day": True,
    }
    analyst = {"rec_buy": 10, "rec_sell": 1, "insider_buys": 2, "insider_sells": 0}
    out = compute_signal_score("AAPL", tech, {"trail_pe": 12}, analyst, {"sentiment_score": 0.8})
    bd = out["breakdown"]
    assert bd == {
        "rsi": 2.0,
        "macd": 2.0,
        "bollinger": 1.0,
        "ema_cross": 1.5,
        "volume": 0.5,
        "pe_ratio": 1.0,
        "analyst_consensus": 1.0,
        "insider_activity": 0.5,
        "news_sentiment": 0.8,
    }
    assert out["score"] == pytest.approx(10.0)  # 10.3 clamped to the +10 ceiling
    assert out["signal"] == "BUY"
    assert "MACD bullish crossover" in out["reasoning"]


def test_bearish_components():
    tech = {
        "rsi": 80,
        "macd_label": "BEARISH CROSS",
        "bb_label": "NEAR UPPER",
        "ema_label": "DEATH CROSS",
        "vol_label": "HIGH VOLUME",
        "vol_up_day": False,
    }
    out = compute_signal_score("AAPL", tech, {"trail_pe": 60}, {"rec_buy": 1, "rec_sell": 5}, {"sentiment_score": -2.0})
    assert out["breakdown"]["news_sentiment"] == -1.0  # clamped
    assert out["score"] == pytest.approx(-10.0)
    assert out["signal"] == "SELL"


def test_missing_news_and_pe_are_neutral():
    out = compute_signal_score("AAPL", NEUTRAL_TECH, {}, {}, None)
    assert out["breakdown"]["pe_ratio"] == 0.0 and out["breakdown"]["news_sentiment"] == 0.0


@pytest.mark.parametrize(
    "score,signal",
    [
        (3.1, "BUY"),
        (3.0, "TRIM"),
        (1.1, "TRIM"),
        (1.0, "HOLD"),
        (-1.0, "HOLD"),
        (-1.1, "WATCH"),
        (-3.0, "WATCH"),
        (-3.1, "SELL"),
    ],
)
def test_score_to_signal_thresholds(score, signal):
    assert score_to_signal(score) == signal


def test_holding_overrides_take_precedence():
    bullish = {"rsi": 25, "macd_label": "BULLISH CROSS"}
    out = compute_signal_score("OKLO", bullish, {}, {}, {}, price=90)
    assert out["signal"] == "SELL" and "take profit" in out["reasoning"]

    out = compute_signal_score("VOO", NEUTRAL_TECH, {}, {}, {}, price=600)
    assert out["signal"] == "BUY" and "$615" in out["reasoning"]

    out = compute_signal_score("EWY", NEUTRAL_TECH, {}, {}, {}, price=99, hi52=100)
    assert out["signal"] == "TRIM" and "52W high" in out["reasoning"]

    out = compute_signal_score("SCHD", NEUTRAL_TECH, {}, {}, {}, price=28, day_chg=-1)
    assert out["signal"] == "HOLD"  # no rule fires: falls back to the score


def test_signal_logic_rules():
    assert signal_logic("OKLO", 60, 0, None, 0, None)[0] == "WATCH"
    assert signal_logic("VOO", 650, 5, None, -2.5, None)[0] == "BUY"
    assert signal_logic("VOO", 650, 5, None, 0, None) == ("HOLD", "Long-term compounding in progress")
    assert signal_logic("EWY", 90, 30, None, 0, 120)[0] == "TRIM"
    assert signal_logic("AAPL", 200, 40, 40, 0, None)[0] == "SELL"
    assert signal_logic("BAC", 40, 0, 11, 0, None) == ("BUY", "Deep value -- PE 11.0")
    assert signal_logic("BAC", 40, 0, 20, -6, None)[0] == "SELL"


# ---------------------------------------------------------------- trade plan


@pytest.mark.parametrize("strategy", ["RSI_MACD", "GOLDEN_CROSS", "INSTITUTIONAL", "MANUAL"])
@pytest.mark.parametrize(
    "cfg",
    [
        {},
        {"cfg_entry": 95.0},
        {"cfg_entry": 150.0},
        {"cfg_stop": 99.5},
        {"cfg_stop": 150.0},
        {"cfg_target": 101.0},
        {"cfg_target": 140.0},
    ],
)
def test_trade_levels_invariants(strategy, cfg):
    lv = compute_trade_levels(100.0, 2.0, strategy, **cfg)
    assert lv["stop"] < lv["entry"] < lv["target"]
    assert lv["rr"] >= 2.0 - 1e-6


def test_limit_entry_sits_below_market_and_breakout_above():
    assert compute_trade_levels(100.0, 2.0, "RSI_MACD")["entry"] == 99.2
    assert compute_trade_levels(100.0, 2.0, "GOLDEN_CROSS")["entry"] == 100.5


def test_stale_configured_limit_is_reset():
    # A configured limit above the market would fill instantly; it gets reset under price.
    assert compute_trade_levels(100.0, 2.0, "RSI_MACD", cfg_entry=120.0)["entry"] == 99.2
    assert compute_trade_levels(100.0, 2.0, "RSI_MACD", cfg_entry=97.0)["entry"] == 97.0


def test_missing_atr_falls_back_to_two_percent():
    lv = compute_trade_levels(100.0, None, "RSI_MACD")
    assert lv["stop"] == pytest.approx(99.2 - 1.5 * 2.0)


@pytest.mark.parametrize(
    "entry,stop,expected",
    [
        (100, 98, 50),
        (100, 100, 1),
        (100, 101, 1),
        (None, 98, 1),
        (100, float("nan"), 1),
        (1000, 999.99, 10000),
    ],
)
def test_position_size(entry, stop, expected):
    assert compute_position_size(entry, stop, account_size=10_000) == expected


def test_pick_status():
    assert pick_status(100, 99.5, is_breakout=False) == "ACTIVE"
    assert pick_status(104, 99.5, is_breakout=False) == "WATCH"
    assert pick_status(110, 99.5, is_breakout=False) == "PENDING"
    assert pick_status(100, 100.5, is_breakout=True) == "ACTIVE"


def test_fill_guidance_wording():
    assert "NOW" in fill_guidance(100, 100, is_breakout=False)
    assert "intraday dip" in fill_guidance(100, 99.2, is_breakout=False)
    assert "enter at market" in fill_guidance(101, 100.5, is_breakout=True)
    assert "monitor" in fill_guidance(100, 110, is_breakout=True)


def test_holding_action():
    today = dt.date(2026, 11, 13)
    assert holding_action("HOLD", 10, 100, 10_000, today) == "Thesis intact. Next review: December 13, 2026"
    assert holding_action("TRIM", 13, 100, 10_000, today).startswith("Sell 3 shares")
    assert holding_action("BUY", 10, 100, 10_000, today) == "Add 50 shares. Limit order at: $99.50"
    assert holding_action("BUY", 10, 0, 10_000, today).startswith("Add 1 shares")  # no ZeroDivisionError


def test_holding_timeline_generic_and_named():
    generic = holding_timeline("AAPL", 100, {"atr_stop": 95, "atr_target": 110, "bb_label": "MID RANGE"}, {})
    assert generic["short_trigger"] == "Stop loss at $95.00 (ATR-based)"
    assert generic["med_catalyst"] == "Next earnings: TBD"
    named = holding_timeline("VOO", 600, {}, {"next_earnings": dt.date(2027, 1, 20)})
    assert named["short_trigger"] == "Buy more if price dips below $615"
    assert named["med_catalyst"] == "Next earnings: Jan 20"


# ---------------------------------------------------------------- risk


def _holding(tk, value, beta, sector):
    return {"ticker": tk, "market_value": value, "fins": {"beta": beta, "sector": sector}}


def test_portfolio_risk_weights_and_sectors():
    holdings = [_holding("A", 6000, 1.5, "Technology"), _holding("B", 4000, 0.5, "Utilities")]
    rets = {"A": np.array([0.01, -0.02, 0.03]), "B": np.array([0.0, 0.01, -0.01])}
    out = portfolio_risk(holdings, rets)
    assert out["weighted_beta"] == pytest.approx(1.1)
    assert out["risk_rating"] == "MEDIUM"
    assert out["sectors"] == {"Technology": pytest.approx(60.0), "Utilities": pytest.approx(40.0)}
    assert out["positions"][0] == {"ticker": "A", "weight": 60.0, "beta": 1.5, "risk_1d": 180.0}
    assert out["var_95"] > 0


def test_portfolio_risk_missing_beta_defaults_to_one():
    out = portfolio_risk([_holding("A", 100, None, "X")], {})
    assert out["weighted_beta"] == 1.0 and out["var_95"] == 0


def test_portfolio_risk_empty():
    assert portfolio_risk([], {})["risk_rating"] == "N/A"


def test_historical_var_is_fifth_percentile_loss():
    rets = np.linspace(-0.05, 0.05, 101)
    assert historical_var([(1.0, rets)], 10_000) == pytest.approx(0.045 * 10_000)


def test_historical_var_aligns_most_recent_observations():
    long = np.array([0.5, 0.5, -0.01, -0.01])  # old outliers must be ignored
    short = np.array([-0.01, -0.01])
    assert historical_var([(0.5, long), (0.5, short)], 100) == pytest.approx(1.0)


@pytest.mark.parametrize("beta,rating", [(0.79, "LOW"), (0.8, "MEDIUM"), (1.19, "MEDIUM"), (1.2, "HIGH")])
def test_risk_rating(beta, rating):
    assert risk_rating(beta) == rating


# ---------------------------------------------------------------- proxies


def test_proxy_scores_renormalise_missing_proxies():
    weights = {"Co": {"A": 0.5, "B": 0.5}}
    assert compute_proxy_scores({"A": {"momentum_5d": 0.04}}, weights) == {"Co": 0.04}
    assert compute_proxy_scores({"A": {"momentum_5d": 0.04}, "B": {"momentum_5d": 0.0}}, weights) == {"Co": 0.02}
    assert compute_proxy_scores({}, weights) == {}


def test_space_index():
    prices = {"RKLB": {"momentum_5d": 0.1}, "ASTS": {"momentum_5d": -0.1}, "LUNR": {"momentum_5d": 0.3}}
    assert build_space_economy_index(prices) == pytest.approx(0.1)
    assert build_space_economy_index({}) is None


# ---------------------------------------------------------------- valuation


@pytest.mark.parametrize(
    "pe,growth,expected", [(20, 0.25, 0.8), (20, 10, 2.0), (20, 0, None), (None, 0.2, None), (20, -0.1, None)]
)
def test_peg_ratio(pe, growth, expected):
    assert peg_ratio(pe, growth) == expected


def test_labels():
    assert peg_label(0.8) == "UNDERVALUED" and peg_label(1.5) == "FAIR" and peg_label(3) == "EXPENSIVE"
    assert peg_label(None) == "N/A"
    assert altman_label(3.5) == "SAFE" and altman_label(2.0) == "GREY ZONE" and altman_label(1.0) == "DISTRESS"


def test_altman_z():
    z = altman_z(
        working_capital=20,
        retained_earnings=30,
        ebit=10,
        market_cap=200,
        total_liabilities=100,
        revenue=150,
        total_assets=100,
    )
    assert z == pytest.approx(1.2 * 0.2 + 1.4 * 0.3 + 3.3 * 0.1 + 0.6 * 2.0 + 1.0 * 1.5, abs=0.01)
    assert altman_z(1, 1, 1, 1, 1, 1, total_assets=0) is None


def test_estimate_revision_label():
    assert estimate_revision_label([{"epsAvg": 1.10}, {"epsAvg": 1.00}]) == "ESTIMATES RISING"
    assert estimate_revision_label([{"epsAvg": 0.90}, {"epsAvg": 1.00}]) == "ESTIMATES FALLING"
    assert estimate_revision_label([{"epsAvg": 1.02}, {"epsAvg": 1.00}]) == "STABLE"
    assert estimate_revision_label([{"epsAvg": 1.0}]) == "N/A"
    assert estimate_revision_label([{"epsAvg": 1.0}, {"epsAvg": 0}]) == "N/A"


def test_earnings_surprise_and_market_cap():
    assert earnings_surprise_pct(1.1, 1.0) == 10.0
    assert earnings_surprise_pct(1.1, 0) is None
    assert format_market_cap(2.5e12) == "$2.50T"
    assert format_market_cap(3.2e9) == "$3.20B"
    assert format_market_cap(4.5e6) == "$4.5M"
    assert format_market_cap(None) == "N/A"
