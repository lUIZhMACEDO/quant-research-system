"""Full-history indicators and the per-ticker technical snapshot, on synthetic price paths."""

import numpy as np
import pandas as pd
import pytest

from conftest import make_ohlcv
from quant_research.signals.indicators import compute_indicator_frame, hurst_rs, rolling_hurst
from quant_research.signals.technicals import (
    EMPTY_SNAPSHOT,
    bollinger_label,
    macd_cross_label,
    rsi_label,
    support_resistance,
    technical_snapshot,
)

# ---------------------------------------------------------------- indicator frame


def test_indicator_frame_has_every_stored_column(rising_close):
    from quant_research.storage.db import INDICATOR_COLUMNS

    out = compute_indicator_frame(make_ohlcv(rising_close))
    missing = set(INDICATOR_COLUMNS) - {"ticker", "date"} - set(out.columns)
    assert not missing


def test_indicator_frame_does_not_mutate_input(rising_close):
    df = make_ohlcv(rising_close)
    cols = list(df.columns)
    compute_indicator_frame(df)
    assert list(df.columns) == cols


def test_momentum_matches_pct_change(rising_close):
    df = make_ohlcv(rising_close)
    out = compute_indicator_frame(df)
    expected = df["close"].iloc[-1] / df["close"].iloc[-6] - 1
    assert out["momentum_5d"].iloc[-1] == pytest.approx(expected)


def test_uptrend_sets_golden_cross_and_high_rsi(rising_close):
    out = compute_indicator_frame(make_ohlcv(rising_close))
    last = out.iloc[-1]
    assert last["golden_cross"] == 1
    assert last["sma_50"] > last["sma_200"]
    assert last["rsi_14"] > 60
    assert 0 <= last["bb_pct"] <= 1.5


def test_cross_signal_marks_the_crossing_bar():
    # Fall for 220 bars then rally hard: SMA50 crosses above SMA200 exactly once.
    close = np.concatenate([np.linspace(200, 100, 220), np.linspace(100, 260, 120)])
    out = compute_indicator_frame(make_ohlcv(close))
    assert (out["cross_signal"] == 1).sum() == 1
    assert out["cross_signal"].isin([-1, 0, 1]).all()


def test_realized_vol_is_annualised():
    rng = np.random.default_rng(3)
    daily = rng.normal(0, 0.01, 300)
    close = 100 * np.cumprod(1 + daily)
    out = compute_indicator_frame(make_ohlcv(close))
    assert out["realized_vol_21d"].iloc[-1] == pytest.approx(0.01 * np.sqrt(252), rel=0.5)


# ---------------------------------------------------------------- Hurst


def test_hurst_separates_trending_from_mean_reverting():
    rng = np.random.default_rng(0)
    trend = np.linspace(100, 150, 64) + rng.normal(0, 0.05, 64)
    mean_reverting = 100 + np.tile([1.0, -1.0], 32) + rng.normal(0, 0.05, 64)
    assert hurst_rs(trend) > 0.5 > hurst_rs(mean_reverting)


def test_hurst_needs_enough_lags():
    assert hurst_rs(np.arange(10, dtype=float)) is None


def test_rolling_hurst_is_nan_until_first_full_window():
    s = pd.Series(np.linspace(100, 200, 100))
    h = rolling_hurst(s, window=64)
    assert h.iloc[:64].isna().all()
    assert h.iloc[64:].notna().all()


def test_rolling_hurst_flat_series_stays_nan():
    h = rolling_hurst(pd.Series(np.full(80, 100.0)), window=64)
    assert h.isna().all()


# ---------------------------------------------------------------- snapshot


def test_snapshot_needs_26_bars():
    df = make_ohlcv(np.linspace(100, 110, 25), capitalised=True)
    assert technical_snapshot(df) == EMPTY_SNAPSHOT
    assert technical_snapshot(pd.DataFrame()) == EMPTY_SNAPSHOT


def test_snapshot_uptrend(rising_close):
    snap = technical_snapshot(make_ohlcv(rising_close[-90:], capitalised=True))
    assert snap["rsi_label"] in {"OVERBOUGHT", "NEUTRAL"} and snap["rsi"] > 55
    assert snap["ema_label"] == "GOLDEN CROSS"
    assert snap["atr_stop"] < rising_close[-1] < snap["atr_target"]
    assert snap["vwap_label"] == "ABOVE VWAP"


def test_snapshot_downtrend(falling_close):
    snap = technical_snapshot(make_ohlcv(falling_close[-90:], capitalised=True))
    assert snap["rsi"] < 45
    assert snap["ema_label"] == "DEATH CROSS"
    assert snap["vwap_label"] == "BELOW VWAP"


def test_snapshot_reads_fixture_file(spy_fixture):
    snap = technical_snapshot(spy_fixture)
    assert snap["rsi"] is not None
    assert snap["ema_label"] == "N/A"  # 30 bars < 50 needed for EMA20/50
    assert snap["vol_label"] in {"NORMAL", "HIGH VOLUME"}


def test_high_volume_up_and_down_days():
    close = np.linspace(100, 120, 90)
    df = make_ohlcv(close, capitalised=True)
    df.iloc[-1, df.columns.get_loc("Volume")] = 5_000_000
    snap = technical_snapshot(df)
    assert snap["vol_label"] == "HIGH VOLUME" and snap["vol_up_day"] is True

    df.iloc[-1, df.columns.get_loc("Close")] = close[-2] - 1
    assert technical_snapshot(df)["vol_up_day"] is False


@pytest.mark.parametrize("rsi,label", [(70.1, "OVERBOUGHT"), (70, "NEUTRAL"), (30, "NEUTRAL"), (29.9, "OVERSOLD")])
def test_rsi_label_boundaries(rsi, label):
    assert rsi_label(rsi) == label


def test_macd_cross_label():
    assert macd_cross_label(pd.Series([-1.0, 1.0]), pd.Series([0.0, 0.0])) == "BULLISH CROSS"
    assert macd_cross_label(pd.Series([1.0, -1.0]), pd.Series([0.0, 0.0])) == "BEARISH CROSS"
    assert macd_cross_label(pd.Series([1.0, 2.0]), pd.Series([0.0, 0.0])) == "NEUTRAL"
    assert macd_cross_label(pd.Series([1.0]), pd.Series([0.0])) == "NEUTRAL"


def test_bollinger_label():
    assert bollinger_label(99, upper=100, lower=80) == "NEAR UPPER"
    assert bollinger_label(81, upper=100, lower=80) == "NEAR LOWER"
    assert bollinger_label(90, upper=100, lower=80) == "MID RANGE"


def test_support_resistance_finds_repeated_levels():
    # Price oscillates between ~95 and ~105 several times, then sits just above support.
    wave = np.tile(np.concatenate([np.linspace(95, 105, 6), np.linspace(105, 95, 6)[1:-1]]), 6)
    df = pd.DataFrame({"High": wave + 0.5, "Low": wave - 0.5})
    support, resistance, label = support_resistance(df, price=95.5)
    assert support == pytest.approx(94.5, abs=0.6)
    assert resistance == pytest.approx(105.5, abs=0.6)
    assert label == "NEAR SUPPORT"
