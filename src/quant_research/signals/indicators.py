"""Full-history technical indicators for the EOD store, computed in one vectorised pass."""

from __future__ import annotations

import numpy as np
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import MACD, EMAIndicator, SMAIndicator
from ta.volatility import AverageTrueRange, BollingerBands

TRADING_DAYS = 252


def compute_indicator_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Add every indicator column used by the ``indicators`` table to a copy of ``df``.

    ``df`` needs ``open/high/low/close/volume`` columns indexed by date.
    """
    df = df.copy()
    close, high, low, vol = df["close"], df["high"], df["low"], df["volume"]

    # RSI and its z-score versus the trailing year
    df["rsi_14"] = RSIIndicator(close, window=14).rsi()
    rsi_roll = df["rsi_14"].rolling(TRADING_DAYS)
    df["rsi_zscore_252"] = (df["rsi_14"] - rsi_roll.mean()) / rsi_roll.std()

    macd = MACD(close)
    df["macd"] = macd.macd()
    df["macd_signal"] = macd.macd_signal()
    df["macd_hist"] = macd.macd_diff()

    bb = BollingerBands(close, window=20, window_dev=2)
    df["bb_upper"] = bb.bollinger_hband()
    df["bb_lower"] = bb.bollinger_lband()
    df["bb_mid"] = bb.bollinger_mavg()
    df["bb_pct"] = bb.bollinger_pband()  # 0 = lower band, 1 = upper band

    df["sma_50"] = SMAIndicator(close, window=50).sma_indicator()
    df["sma_200"] = SMAIndicator(close, window=200).sma_indicator()
    df["ema_20"] = EMAIndicator(close, window=20).ema_indicator()

    # Golden / death cross: +1 on the bar SMA50 crosses above SMA200, -1 below
    df["golden_cross"] = (df["sma_50"] > df["sma_200"]).astype(int)
    df["cross_signal"] = df["golden_cross"].diff().fillna(0)

    atr = AverageTrueRange(high, low, close, window=14)
    df["atr_14"] = atr.average_true_range()
    df["atr_pct"] = df["atr_14"] / close

    df["realized_vol_21d"] = close.pct_change().rolling(21).std() * np.sqrt(TRADING_DAYS)

    for days in (5, 21, 63, 252):
        df[f"momentum_{days}d"] = close.pct_change(days)

    vol_roll = vol.rolling(20)
    df["vol_zscore_20d"] = (vol - vol_roll.mean()) / vol_roll.std()

    df["hurst_64"] = rolling_hurst(close, window=64)

    # Cross-sectional ranks are filled at portfolio level, not per ticker
    df["rsi_rank"] = np.nan
    df["mom_rank"] = np.nan
    return df


def hurst_rs(chunk: np.ndarray, max_lag: int = 20) -> float | None:
    """Simplified rescaled-range (R/S) Hurst estimate for one window.

    H > 0.5 trending, H < 0.5 mean-reverting, H ~ 0.5 random walk. Needs at least
    four usable lags; returns ``None`` otherwise.
    """
    window = len(chunk)
    rs_vals: list[tuple[int, float]] = []
    for lag in range(2, min(max_lag, window // 4)):
        sub = chunk[:lag]
        dev = np.cumsum(sub - np.mean(sub))
        r = np.max(dev) - np.min(dev)
        s = np.std(sub, ddof=1)
        if s > 0 and r > 0:
            rs_vals.append((lag, r / s))
    if len(rs_vals) < 4:
        return None
    lags = np.log([x[0] for x in rs_vals])
    rs = np.log([x[1] for x in rs_vals])
    return round(float(np.polyfit(lags, rs, 1)[0]), 4)


def rolling_hurst(series: pd.Series, window: int = 64) -> pd.Series:
    """Hurst estimate over a trailing ``window`` bars; NaN until the first full window."""
    arr = series.to_numpy(dtype=float)
    out = np.full(len(arr), np.nan)
    for i in range(window, len(arr)):
        h = hurst_rs(arr[i - window : i])
        if h is not None:
            out[i] = h
    return pd.Series(out, index=series.index)
