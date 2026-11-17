"""Point-in-time technical snapshot for one ticker, used by the screens and the report.

Input is a daily OHLCV frame with yfinance's capitalised columns
(``Open/High/Low/Close/Volume``); output is a dict of values and labels. Pure
function: no I/O, so it is tested directly against synthetic price paths.
"""

from __future__ import annotations

import pandas as pd
from ta.momentum import RSIIndicator, StochRSIIndicator
from ta.trend import MACD, EMAIndicator
from ta.volatility import AverageTrueRange, BollingerBands
from ta.volume import OnBalanceVolumeIndicator

MIN_BARS = 26

EMPTY_SNAPSHOT: dict = {
    "rsi": None,
    "rsi_label": "N/A",
    "stoch_rsi": None,
    "stoch_rsi_label": "N/A",
    "macd_label": "NEUTRAL",
    "bb_label": "N/A",
    "ema_label": "N/A",
    "vol_label": "N/A",
    "atr": None,
    "atr_stop": None,
    "atr_target": None,
    "vwap": None,
    "vwap_label": "N/A",
    "obv_trend": "N/A",
    "support": None,
    "resistance": None,
    "sr_label": "N/A",
}


def rsi_label(rsi: float) -> str:
    if rsi > 70:
        return "OVERBOUGHT"
    if rsi < 30:
        return "OVERSOLD"
    return "NEUTRAL"


def macd_cross_label(macd_line: pd.Series, signal_line: pd.Series) -> str:
    """BULLISH/BEARISH CROSS only on the bar where the lines actually cross."""
    if len(macd_line) < 2 or len(signal_line) < 2:
        return "NEUTRAL"
    m1, m0 = macd_line.iloc[-1], macd_line.iloc[-2]
    s1, s0 = signal_line.iloc[-1], signal_line.iloc[-2]
    if m1 > s1 and m0 <= s0:
        return "BULLISH CROSS"
    if m1 < s1 and m0 >= s0:
        return "BEARISH CROSS"
    return "NEUTRAL"


def bollinger_label(price: float, upper: float, lower: float) -> str:
    if price > upper * 0.98:
        return "NEAR UPPER"
    if price < lower * 1.02:
        return "NEAR LOWER"
    return "MID RANGE"


def support_resistance(
    df: pd.DataFrame, price: float, tolerance: float = 0.01, min_touches: int = 3
) -> tuple[float | None, float | None, str]:
    """Nearest support/resistance from swing pivots that were touched ``min_touches`` times.

    A pivot low (high) is lower (higher) than the two bars on each side. Pivots
    within ``tolerance`` of each other count as touches of the same level.
    """
    highs = df["High"].to_numpy()
    lows = df["Low"].to_numpy()
    levels: list[float] = []
    for i in range(2, len(df) - 2):
        if lows[i] < min(lows[i - 1], lows[i - 2], lows[i + 1], lows[i + 2]):
            levels.append(float(lows[i]))
        if highs[i] > max(highs[i - 1], highs[i - 2], highs[i + 1], highs[i + 2]):
            levels.append(float(highs[i]))

    sr_levels: list[float] = []
    used: list[float] = []
    for lv in sorted(levels):
        if any(abs(lv - u) / u < tolerance for u in used):
            continue
        touches = sum(1 for x in levels if abs(x - lv) / lv < tolerance)
        if touches >= min_touches:
            sr_levels.append(lv)
            used.append(lv)

    supports = [lv for lv in sr_levels if lv < price]
    resistances = [lv for lv in sr_levels if lv > price]
    support = round(max(supports), 2) if supports else None
    resistance = round(min(resistances), 2) if resistances else None
    if support and abs(price - support) / price < 0.02:
        label = "NEAR SUPPORT"
    elif resistance and abs(resistance - price) / price < 0.02:
        label = "NEAR RESISTANCE"
    else:
        label = "MID RANGE"
    return support, resistance, label


def technical_snapshot(df: pd.DataFrame) -> dict:
    """RSI, StochRSI, MACD, Bollinger, EMA 20/50, ATR stop/target, VWAP, OBV and S/R.

    Returns :data:`EMPTY_SNAPSHOT` (a copy) when there are fewer than
    :data:`MIN_BARS` bars or the core calculation fails.
    """
    if df is None or df.empty or len(df) < MIN_BARS:
        return dict(EMPTY_SNAPSHOT)
    close = df["Close"]
    cur = float(close.iloc[-1])
    try:
        rsi_val = float(RSIIndicator(close=close, window=14).rsi().iloc[-1])

        stoch_rsi_val, stoch_rsi_lbl = None, "N/A"
        try:
            srsi = StochRSIIndicator(close=close, window=14, smooth1=3, smooth2=3)
            stoch_rsi_val = round(float(srsi.stochrsi().iloc[-1]), 3)
            if stoch_rsi_val < 0.2:
                stoch_rsi_lbl = "OVERSOLD"
            elif stoch_rsi_val > 0.8:
                stoch_rsi_lbl = "OVERBOUGHT"
            else:
                stoch_rsi_lbl = "NEUTRAL"
        except Exception:
            pass

        macd_obj = MACD(close=close, window_slow=26, window_fast=12, window_sign=9)
        macd_lbl = macd_cross_label(macd_obj.macd(), macd_obj.macd_signal())

        bb = BollingerBands(close=close, window=20, window_dev=2)
        bb_lbl = bollinger_label(cur, bb.bollinger_hband().iloc[-1], bb.bollinger_lband().iloc[-1])

        # EMA 20/50 needs 50 bars for a meaningful cross
        if len(close) >= 50:
            ema20 = EMAIndicator(close=close, window=20).ema_indicator().iloc[-1]
            ema50 = EMAIndicator(close=close, window=50).ema_indicator().iloc[-1]
            ema_lbl = "GOLDEN CROSS" if ema20 > ema50 else "DEATH CROSS"
        else:
            ema_lbl = "N/A"

        atr_val = float(
            AverageTrueRange(high=df["High"], low=df["Low"], close=close, window=14).average_true_range().iloc[-1]
        )
        atr_stop = round(cur - 1.5 * atr_val, 2)
        atr_tgt = round(cur + 2.5 * atr_val, 2)

        vol_20 = df["Volume"].tail(20).mean()
        vol_lbl = "HIGH VOLUME" if df["Volume"].iloc[-1] > 1.5 * vol_20 else "NORMAL"
        day_up = bool(close.iloc[-1] >= close.iloc[-2]) if len(close) >= 2 else True

        # VWAP over the last 20 sessions
        vwap_val, vwap_lbl = None, "N/A"
        try:
            recent = df.tail(20)
            tp = (recent["High"] + recent["Low"] + recent["Close"]) / 3
            vwap_val = round(float((tp * recent["Volume"]).cumsum().iloc[-1] / recent["Volume"].cumsum().iloc[-1]), 2)
            vwap_lbl = "ABOVE VWAP" if cur > vwap_val else "BELOW VWAP"
        except Exception:
            pass

        # OBV 10-day slope
        obv_trend = "N/A"
        try:
            obv = OnBalanceVolumeIndicator(close=close, volume=df["Volume"]).on_balance_volume().tail(10)
            if len(obv) >= 10:
                obv_trend = "ACCUMULATION" if obv.iloc[-1] - obv.iloc[0] > 0 else "DISTRIBUTION"
        except Exception:
            pass

        support, resistance, sr_lbl = None, None, "N/A"
        try:
            support, resistance, sr_lbl = support_resistance(df, cur)
        except Exception:
            pass

        return {
            "rsi": round(rsi_val, 1),
            "rsi_label": rsi_label(rsi_val),
            "stoch_rsi": stoch_rsi_val,
            "stoch_rsi_label": stoch_rsi_lbl,
            "macd_label": macd_lbl,
            "bb_label": bb_lbl,
            "ema_label": ema_lbl,
            "vol_label": vol_lbl,
            "vol_up_day": day_up,
            "atr": round(atr_val, 2),
            "atr_stop": atr_stop,
            "atr_target": atr_tgt,
            "vwap": vwap_val,
            "vwap_label": vwap_lbl,
            "obv_trend": obv_trend,
            "support": support,
            "resistance": resistance,
            "sr_label": sr_lbl,
        }
    except Exception:
        return dict(EMPTY_SNAPSHOT)
