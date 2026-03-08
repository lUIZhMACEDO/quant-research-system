"""
Local AI Stock Analyst  --  v3.1.0
==================================
Full-stack daily report: portfolio tracking, Smart Picks with strategy
detection, technical indicators, financial metrics, earnings catalysts,
macro/political risk, and a portfolio risk dashboard.

Data: Yahoo Finance, Finnhub, Finviz, Google News RSS.
Schedule: Windows Task Scheduler -- Mon-Fri at 07:30.
"""

# =====================================================================
#  IMPORTS
# =====================================================================
import json
import os, sys, io, subprocess, smtplib, time, math
import datetime
from datetime import timedelta
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from difflib import SequenceMatcher

import numpy as np
import pandas as pd
import requests
import yfinance as yf
import feedparser
from dotenv import load_dotenv

from ta.momentum import RSIIndicator, StochRSIIndicator
from ta.trend import MACD as MACDCalc, EMAIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from ta.volume import OnBalanceVolumeIndicator

# Optional imports -- degrade gracefully
try:
    import finnhub as _fh_mod
except ImportError:
    _fh_mod = None

try:
    from pyfinviz.stock import Stock as _FinvizStock
    _HAS_FINVIZ = True
except Exception:
    _HAS_FINVIZ = False

try:
    import streamlit as st
except ImportError:
    st = None

# Windows encoding fix
if sys.stdout and hasattr(sys.stdout, "encoding"):
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# =====================================================================
#  1. CONFIGURATION
# =====================================================================
load_dotenv()

EMAIL_PASSWORD  = os.getenv("EMAIL_PASSWORD")
SENDER_EMAIL    = os.getenv("SENDER_EMAIL")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL")
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

SCHEDULE_TIME      = "07:30"
ACCOUNT_SIZE       = 10_000
RATE_LIMIT_DELAY   = 0.30          # seconds between Finnhub calls

# -- Finnhub client (None if key missing) --
_fh: object | None = None
if FINNHUB_API_KEY and _fh_mod:
    try:
        _fh = _fh_mod.Client(api_key=FINNHUB_API_KEY)
    except Exception:
        _fh = None

# -- YOUR PORTFOLIO --
MY_PORTFOLIO = [
    {"ticker": "OKLO",  "shares": 14,  "avg_cost": 62.90},
    {"ticker": "EWY",   "shares": 13,  "avg_cost": 114.11},
    {"ticker": "SCHD",  "shares": 18,  "avg_cost": 28.53},
    {"ticker": "VOO",   "shares": 6,   "avg_cost": 631.55},
]

PORTFOLIO_STRATEGIES = {
    "OKLO": "Hold until July 2026 DOE milestones; Sell if >$85.",
    "VOO":  "Core position. Buy more if price dips below $615.",
    "SCHD": "Dividend play. Reinvest distributions quarterly.",
    "EWY":  "Take 25% profit now; South Korea index is at 52W highs.",
}

ALERT_RULES = {
    "OKLO":  {"price_move_pct": 3.0, "min_score_change": 3, "earnings_days": 2},
    "VOO":   {"price_move_pct": 2.0, "min_score_change": 4, "earnings_days": 1},
    "EWY":   {"price_move_pct": 3.0, "min_score_change": 3, "earnings_days": 2},
    "SCHD":  {"price_move_pct": 2.5, "min_score_change": 4, "earnings_days": 2},
    "_default": {"price_move_pct": 3.0, "min_score_change": 3, "earnings_days": 2},
}
SCORES_CACHE_FILE = Path(__file__).parent / "scores_cache.json"
ALERTS_FILE = Path(__file__).parent / "alerts.json"

# -- SMART PICKS --
MOMENTUM_PICKS = [
    {"ticker": "AMD", "name": "Advanced Micro Devices",
     "strategy_type": "RSI_MACD",
     "reason": "New Meta Platforms deal for 6GW of GPU infrastructure. "
               "Fundamental shift in AI capex, not a retail pump.",
     "entry": 213.50, "target": 235.00, "stop": 202.00},
    {"ticker": "HD", "name": "Home Depot",
     "strategy_type": "GOLDEN_CROSS",
     "reason": "Earnings beat ($2.72 vs $2.53 expected). "
               "Breaking out of a 3-month consolidation pattern.",
     "entry": 412.00, "target": 435.00, "stop": 401.00},
]

SWING_PICKS = [
    {"ticker": "ZBH", "name": "Zimmer Biomet",
     "strategy_type": "BB_MEAN_REVERSION",
     "reason": "Currently 34% undervalued relative to fair value ($130). "
               "Solid value-rotation play for Q2 2026.",
     "entry": 85.00, "target": 110.00, "stop": 79.00},
    {"ticker": "PEP", "name": "PepsiCo",
     "strategy_type": "INSTITUTIONAL",
     "reason": "High institutional Put-Selling rank (100/100). "
               "Heavy support at the $165 level.",
     "entry": 168.00, "target": 182.00, "stop": 162.00},
    {"ticker": "TMUS", "name": "T-Mobile US",
     "strategy_type": "RSI_MACD",
     "reason": "Strong relative strength during the recent AI-led dip. "
               "Approaching major psychological breakout at $225.",
     "entry": 220.00, "target": 245.00, "stop": 211.00},
]

STRATEGY_TIMELINE = [
    {"period": "Immediate", "action": "Execute EWY Trim",
     "detail": "Lock in 26% gain on international ETF. Prudent given new "
               "10% global tariff uncertainty."},
    {"period": "This Week", "action": "Monitor NVDA Earnings (Wed)",
     "detail": "Nvidia results will dictate whether OKLO and VOO face a "
               "sector-wide AI correction."},
    {"period": "April 2026", "action": "Trim OKLO if >$82",
     "detail": "Likely volatility spike before Q1 earnings. Lock in any "
               "gains above $80."},
    {"period": "Late 2026", "action": "Accumulate SCHD",
     "detail": "Value stocks are predicted to outperform tech in H2 2026."},
    {"period": "July 2026", "action": "OKLO DOE Deadline",
     "detail": "If they miss the criticality milestone the stock will "
               "likely retrace to the $40 range."},
]

# Tickers to check for earnings this week
WATCHLIST = ["NVDA", "AAPL", "MSFT", "GOOGL", "META", "AMZN", "TSLA", "JPM"]

MACRO_KEYWORDS = {
    "tariff":       {"tickers": ["EWY"],  "level": "HIGH",   "reason": "International trade risk"},
    "china":        {"tickers": ["EWY"],  "level": "HIGH",   "reason": "China geopolitical risk"},
    "sanctions":    {"tickers": ["EWY"],  "level": "HIGH",   "reason": "Sanctions risk"},
    "fed":          {"tickers": ["SCHD","VOO"], "level": "MEDIUM", "reason": "Fed policy change"},
    "rate hike":    {"tickers": ["SCHD","VOO"], "level": "MEDIUM", "reason": "Rate hike risk"},
    "rate cut":     {"tickers": ["SCHD","VOO"], "level": "MEDIUM", "reason": "Rate cut signal"},
    "inflation":    {"tickers": ["SCHD","VOO"], "level": "MEDIUM", "reason": "Inflation impact"},
    "recession":    {"tickers": ["*"],    "level": "MEDIUM", "reason": "Recession risk"},
    "gdp":          {"tickers": ["*"],    "level": "MEDIUM", "reason": "GDP growth concern"},
    "war":          {"tickers": ["*"],    "level": "HIGH",   "reason": "Geopolitical conflict"},
    "opec":         {"tickers": ["*"],    "level": "MEDIUM", "reason": "Energy price impact"},
    "earnings miss":{"tickers": ["*"],    "level": "MEDIUM", "reason": "Earnings concern"},
}

SECTOR_ETF_MAP = {
    "OKLO": "NLR",
    "EWY": "EEM",
    "SCHD": "DVY",
    "VOO": "SPY",
    "Technology": "XLK",
    "Healthcare": "XLV",
    "Financials": "XLF",
    "Energy": "XLE",
    "Utilities": "XLU",
    "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP",
    "Industrials": "XLI",
    "Basic Materials": "XLB",
    "Real Estate": "XLRE",
    "Communication Services": "XLC",
}

# =====================================================================
#  2. CACHING & HELPERS
# =====================================================================
def _get_info_impl(ticker: str) -> dict:
    try:
        return yf.Ticker(ticker).info or {}
    except Exception:
        return {}

def _get_hist_impl(ticker: str, period: str, interval: str) -> pd.DataFrame:
    try:
        return yf.Ticker(ticker).history(period=period, interval=interval)
    except Exception:
        return pd.DataFrame()

if st is not None:
    @st.cache_data(ttl=60)
    def get_info(ticker: str) -> dict:
        return _get_info_impl(ticker)

    @st.cache_data(ttl=60)
    def get_hist(ticker: str, period: str = "30d", interval: str = "1d") -> pd.DataFrame:
        return _get_hist_impl(ticker, period, interval)
else:
    def get_info(ticker: str) -> dict:
        return _get_info_impl(ticker)
    def get_hist(ticker: str, period: str = "30d", interval: str = "1d") -> pd.DataFrame:
        return _get_hist_impl(ticker, period, interval)


def fh_call(func_name: str, *args, **kwargs):
    """Rate-limited Finnhub call. Returns None on any failure."""
    if not _fh:
        return None
    fn = getattr(_fh, func_name, None)
    if not fn:
        return None
    try:
        time.sleep(RATE_LIMIT_DELAY)
        return fn(*args, **kwargs)
    except Exception:
        return None


def _similar(a: str, b: str, thresh: float = 0.80) -> bool:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio() > thresh


def get_crypto_prices(coins=None):
    """CoinGecko free API — no key required. Returns price, 24h change, market cap."""
    if coins is None:
        coins = ["bitcoin", "ethereum", "solana", "binancecoin", "ripple"]
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": ",".join(coins),
        "vs_currencies": "usd",
        "include_24hr_change": "true",
        "include_market_cap": "true",
        "include_24hr_vol": "true",
    }
    try:
        r = requests.get(url, params=params, timeout=6)
        return r.json()
    except Exception:
        return {}


def get_fear_greed():
    """Crypto Fear & Greed Index — free, no key required."""
    try:
        r = requests.get("https://api.alternative.me/fng/", timeout=5)
        d = r.json()["data"][0]
        return {"value": int(d["value"]), "label": d["value_classification"]}
    except Exception:
        return {"value": 50, "label": "Neutral"}


def get_ai_strategy_note(ticker: str, signal: str, rsi: float, analyst_buy: int, analyst_sell: int) -> str:
    """Generate a 1-sentence strategy note using Claude. Falls back to PORTFOLIO_STRATEGIES if API fails."""
    try:
        import anthropic as _anthropic
        client = _anthropic.Anthropic()
        prompt = (
            f"Stock: {ticker}. Signal: {signal}. RSI: {rsi:.0f}. "
            f"Analyst ratings: {analyst_buy} buy, {analyst_sell} sell. "
            f"Write one concise sentence (max 20 words) of actionable strategy advice for this position. "
            f"No disclaimers. Plain text only."
        )
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=60,
            messages=[{"role": "user", "content": prompt}]
        )
        return msg.content[0].text.strip()
    except Exception:
        return PORTFOLIO_STRATEGIES.get(ticker, "Monitor position and reassess on next earnings.")


# =====================================================================
#  3. TECHNICAL INDICATORS
# =====================================================================
def compute_technicals(ticker: str) -> dict:
    """Compute RSI, StochRSI, MACD, BB, EMA, ATR, VWAP, OBV, Support/Resistance."""
    empty = {"rsi": None, "rsi_label": "N/A", "stoch_rsi": None, "stoch_rsi_label": "N/A",
             "macd_label": "NEUTRAL", "bb_label": "N/A", "ema_label": "N/A",
             "vol_label": "N/A", "atr": None, "atr_stop": None, "atr_target": None,
             "vwap": None, "vwap_label": "N/A",
             "obv_trend": "N/A",
             "support": None, "resistance": None, "sr_label": "N/A"}
    df = get_hist(ticker, "90d", "1d")
    if df.empty or len(df) < 26:
        return empty
    close = df["Close"]
    cur = close.iloc[-1]
    try:
        # RSI
        rsi_val = RSIIndicator(close=close, window=14).rsi().iloc[-1]
        if rsi_val > 70: rsi_lbl = "OVERBOUGHT"
        elif rsi_val < 30: rsi_lbl = "OVERSOLD"
        else: rsi_lbl = "NEUTRAL"

        # Stochastic RSI
        stoch_rsi_val = None; stoch_rsi_lbl = "N/A"
        try:
            srsi = StochRSIIndicator(close=close, window=14, smooth1=3, smooth2=3)
            stoch_rsi_val = round(srsi.stochrsi().iloc[-1], 3)
            if stoch_rsi_val < 0.2: stoch_rsi_lbl = "OVERSOLD"
            elif stoch_rsi_val > 0.8: stoch_rsi_lbl = "OVERBOUGHT"
            else: stoch_rsi_lbl = "NEUTRAL"
        except Exception:
            pass

        # MACD
        macd_obj = MACDCalc(close=close, window_slow=26, window_fast=12, window_sign=9)
        m_line = macd_obj.macd()
        s_line = macd_obj.macd_signal()
        if len(m_line) >= 2 and len(s_line) >= 2:
            if m_line.iloc[-1] > s_line.iloc[-1] and m_line.iloc[-2] <= s_line.iloc[-2]:
                macd_lbl = "BULLISH CROSS"
            elif m_line.iloc[-1] < s_line.iloc[-1] and m_line.iloc[-2] >= s_line.iloc[-2]:
                macd_lbl = "BEARISH CROSS"
            else:
                macd_lbl = "NEUTRAL"
        else:
            macd_lbl = "NEUTRAL"

        # Bollinger Bands
        bb = BollingerBands(close=close, window=20, window_dev=2)
        upper = bb.bollinger_hband().iloc[-1]
        lower = bb.bollinger_lband().iloc[-1]
        if cur > upper * 0.98: bb_lbl = "NEAR UPPER"
        elif cur < lower * 1.02: bb_lbl = "NEAR LOWER"
        else: bb_lbl = "MID RANGE"

        # EMA 20 / 50 (guard: need 50 bars for valid cross)
        if len(close) >= 50:
            ema20 = EMAIndicator(close=close, window=20).ema_indicator().iloc[-1]
            ema50 = EMAIndicator(close=close, window=50).ema_indicator().iloc[-1]
            ema_lbl = "GOLDEN CROSS" if ema20 > ema50 else "DEATH CROSS"
        else:
            ema_lbl = "N/A"

        # ATR
        atr_obj = AverageTrueRange(high=df["High"], low=df["Low"], close=close, window=14)
        atr_val = atr_obj.average_true_range().iloc[-1]
        atr_stop = round(cur - 1.5 * atr_val, 2)
        atr_tgt  = round(cur + 2.5 * atr_val, 2)

        # Volume
        vol_20 = df["Volume"].tail(20).mean()
        vol_today = df["Volume"].iloc[-1]
        vol_lbl = "HIGH VOLUME" if vol_today > 1.5 * vol_20 else "NORMAL"
        day_up = close.iloc[-1] >= close.iloc[-2] if len(close) >= 2 else True

        # VWAP (last 20 trading days)
        vwap_val = None; vwap_lbl = "N/A"
        try:
            df_vwap = df.tail(20).copy()
            tp = (df_vwap["High"] + df_vwap["Low"] + df_vwap["Close"]) / 3
            cum_tp_vol = (tp * df_vwap["Volume"]).cumsum()
            cum_vol = df_vwap["Volume"].cumsum()
            vwap_series = cum_tp_vol / cum_vol
            vwap_val = round(vwap_series.iloc[-1], 2)
            vwap_lbl = "ABOVE VWAP" if cur > vwap_val else "BELOW VWAP"
        except Exception:
            pass

        # OBV trend (10-day slope)
        obv_trend = "N/A"
        try:
            obv = OnBalanceVolumeIndicator(close=close, volume=df["Volume"]).on_balance_volume()
            obv_10 = obv.tail(10)
            if len(obv_10) >= 10:
                slope = obv_10.iloc[-1] - obv_10.iloc[0]
                obv_trend = "ACCUMULATION" if slope > 0 else "DISTRIBUTION"
        except Exception:
            pass

        # Support / Resistance (scan pivots in last 90 days, 1% tolerance, min 3 touches)
        support = None; resistance = None; sr_lbl = "N/A"
        try:
            highs = df["High"].values
            lows = df["Low"].values
            levels: list[float] = []
            for i in range(2, len(df) - 2):
                if lows[i] < lows[i-1] and lows[i] < lows[i-2] and lows[i] < lows[i+1] and lows[i] < lows[i+2]:
                    levels.append(lows[i])
                if highs[i] > highs[i-1] and highs[i] > highs[i-2] and highs[i] > highs[i+1] and highs[i] > highs[i+2]:
                    levels.append(highs[i])
            sr_levels: list[tuple[float, int]] = []
            used = set()
            for lv in sorted(levels):
                if any(abs(lv - u) / u < 0.01 for u in used):
                    continue
                touches = sum(1 for x in levels if abs(x - lv) / lv < 0.01)
                if touches >= 3:
                    sr_levels.append((lv, touches))
                    used.add(lv)
            supports = [lv for lv, _ in sr_levels if lv < cur]
            resistances = [lv for lv, _ in sr_levels if lv > cur]
            if supports:
                support = round(max(supports), 2)
            if resistances:
                resistance = round(min(resistances), 2)
            if support and abs(cur - support) / cur < 0.02:
                sr_lbl = "NEAR SUPPORT"
            elif resistance and abs(resistance - cur) / cur < 0.02:
                sr_lbl = "NEAR RESISTANCE"
            else:
                sr_lbl = "MID RANGE"
        except Exception:
            pass

        return {"rsi": round(rsi_val, 1), "rsi_label": rsi_lbl,
                "stoch_rsi": stoch_rsi_val, "stoch_rsi_label": stoch_rsi_lbl,
                "macd_label": macd_lbl, "bb_label": bb_lbl,
                "ema_label": ema_lbl, "vol_label": vol_lbl,
                "vol_up_day": day_up,
                "atr": round(atr_val, 2), "atr_stop": atr_stop, "atr_target": atr_tgt,
                "vwap": vwap_val, "vwap_label": vwap_lbl,
                "obv_trend": obv_trend,
                "support": support, "resistance": resistance, "sr_label": sr_lbl}
    except Exception:
        return empty


# =====================================================================
#  4. FINANCIAL METRICS
# =====================================================================
def get_financials(ticker: str) -> dict:
    info = get_info(ticker)
    fwd_pe = info.get("forwardPE")
    trail_pe = info.get("trailingPE")
    pb = info.get("priceToBook")
    ps = info.get("priceToSalesTrailing12Months")
    eps = info.get("trailingEps")
    eg = info.get("earningsGrowth")
    rg = info.get("revenueGrowth")
    pm = info.get("profitMargins")
    dte = info.get("debtToEquity")
    fcf = info.get("freeCashflow")
    beta = info.get("beta")
    div_y = info.get("dividendYield")
    short_pct = info.get("shortPercentOfFloat")
    inst_pct = info.get("heldPercentInstitutions")
    sector = info.get("sector", "Unknown")

    # Finviz backup for short float
    if short_pct is None and _HAS_FINVIZ:
        try:
            fv = _FinvizStock(ticker)
            sf = fv.ticker_fundament.get("Short Float")
            if sf and "%" in str(sf):
                short_pct = float(str(sf).replace("%", "")) / 100
        except Exception:
            pass

    # PEG Ratio
    peg = None
    try:
        if fwd_pe and eg and eg > 0:
            eg_pct = eg * 100 if eg < 1 else eg
            peg = round(fwd_pe / eg_pct, 2) if eg_pct > 0 else None
    except Exception:
        pass
    peg_label = "N/A"
    if peg is not None:
        if peg < 1: peg_label = "UNDERVALUED"
        elif peg <= 2: peg_label = "FAIR"
        else: peg_label = "EXPENSIVE"

    # Altman Z-Score
    z_score = None; z_label = "N/A"
    try:
        tkr = yf.Ticker(ticker)
        bs = tkr.balance_sheet
        inc = tkr.income_stmt
        if bs is not None and not bs.empty and inc is not None and not inc.empty:
            ta_val = bs.loc["Total Assets"].iloc[0] if "Total Assets" in bs.index else None
            if ta_val and ta_val > 0:
                wc = (bs.loc["Current Assets"].iloc[0] - bs.loc["Current Liabilities"].iloc[0]) if "Current Assets" in bs.index and "Current Liabilities" in bs.index else 0
                re = bs.loc["Retained Earnings"].iloc[0] if "Retained Earnings" in bs.index else 0
                ebit = inc.loc["EBIT"].iloc[0] if "EBIT" in inc.index else (inc.loc["Operating Income"].iloc[0] if "Operating Income" in inc.index else 0)
                tl = bs.loc["Total Liabilities Net Minority Interest"].iloc[0] if "Total Liabilities Net Minority Interest" in bs.index else (ta_val - (bs.loc["Total Equity Gross Minority Interest"].iloc[0] if "Total Equity Gross Minority Interest" in bs.index else 0))
                rev = inc.loc["Total Revenue"].iloc[0] if "Total Revenue" in inc.index else 0
                mcap_val = info.get("marketCap") or 0
                x4_denom = tl if tl and tl > 0 else 1
                z_score = round(1.2 * (wc / ta_val) + 1.4 * (re / ta_val) + 3.3 * (ebit / ta_val) + 0.6 * (mcap_val / x4_denom) + 1.0 * (rev / ta_val), 2)
                if z_score > 2.99: z_label = "SAFE"
                elif z_score >= 1.81: z_label = "GREY ZONE"
                else: z_label = "DISTRESS"
    except Exception:
        pass

    # Earnings Estimate Revisions (Finnhub)
    est_revision = "N/A"
    try:
        est_data = fh_call("company_eps_estimates", ticker, freq="quarterly")
        if est_data and isinstance(est_data, dict):
            estimates = est_data.get("data", [])
            if len(estimates) >= 2:
                current_est = estimates[0].get("epsAvg")
                prev_est = estimates[1].get("epsAvg")
                if current_est is not None and prev_est is not None and prev_est != 0:
                    rev_pct = (current_est - prev_est) / abs(prev_est) * 100
                    if rev_pct > 5: est_revision = "ESTIMATES RISING"
                    elif rev_pct < -5: est_revision = "ESTIMATES FALLING"
                    else: est_revision = "STABLE"
    except Exception:
        pass

    return {"fwd_pe": fwd_pe, "trail_pe": trail_pe, "pb": pb, "ps": ps,
            "eps": eps, "earnings_growth": eg, "revenue_growth": rg,
            "profit_margins": pm, "debt_to_equity": dte, "fcf": fcf,
            "beta": beta, "div_yield": div_y, "short_float": short_pct,
            "inst_pct": inst_pct, "sector": sector,
            "peg": peg, "peg_label": peg_label,
            "z_score": z_score, "z_label": z_label,
            "est_revision": est_revision}


# =====================================================================
#  5. EARNINGS & CATALYSTS
# =====================================================================
def get_earnings_info(ticker: str) -> dict:
    """Next earnings date + last quarter surprise."""
    result = {"next_earnings": None, "days_to_earnings": None,
              "last_eps_actual": None, "last_eps_est": None, "last_surprise_pct": None}
    # yfinance calendar
    try:
        cal = yf.Ticker(ticker).calendar
        if cal is not None:
            if isinstance(cal, pd.DataFrame) and "Earnings Date" in cal.columns:
                ed = cal["Earnings Date"].iloc[0]
            elif isinstance(cal, dict):
                ed = cal.get("Earnings Date")
                if isinstance(ed, list) and ed:
                    ed = ed[0]
            else:
                ed = None
            if ed is not None:
                if hasattr(ed, "date"):
                    ed = ed.date() if callable(ed.date) else ed
                if isinstance(ed, datetime.date):
                    result["next_earnings"] = ed
                    result["days_to_earnings"] = (ed - datetime.date.today()).days
    except Exception:
        pass

    # Finnhub last quarter
    data = fh_call("company_earnings", ticker, limit=1)
    if data and isinstance(data, list) and len(data) > 0:
        q = data[0]
        result["last_eps_actual"] = q.get("actual")
        result["last_eps_est"] = q.get("estimate")
        if q.get("actual") is not None and q.get("estimate") and q["estimate"] != 0:
            result["last_surprise_pct"] = round(
                (q["actual"] - q["estimate"]) / abs(q["estimate"]) * 100, 1)
    return result


def get_weekly_catalysts() -> list[dict]:
    """Earnings reports within the next 7 days for watchlist + portfolio + picks."""
    all_tks = set(WATCHLIST)
    for p in MY_PORTFOLIO: all_tks.add(p["ticker"])
    for p in MOMENTUM_PICKS + SWING_PICKS: all_tks.add(p["ticker"])

    catalysts = []
    today = datetime.date.today()
    week = today + timedelta(days=7)

    # Finnhub earnings calendar
    cal = fh_call("earnings_calendar",
                  _from=today.strftime("%Y-%m-%d"),
                  to=week.strftime("%Y-%m-%d"))
    fh_earnings = {}
    if cal and isinstance(cal, dict):
        for ev in cal.get("earningsCalendar", []):
            fh_earnings[ev.get("symbol", "")] = ev

    for tk in sorted(all_tks):
        ei = get_earnings_info(tk)
        dte = ei.get("days_to_earnings")
        if dte is not None and 0 <= dte <= 7:
            est = fh_earnings.get(tk, {}).get("epsEstimate")
            catalysts.append({
                "ticker": tk,
                "date": ei["next_earnings"],
                "days": dte,
                "eps_est": est,
            })
    return catalysts


# =====================================================================
#  6. ANALYST & INSIDER DATA
# =====================================================================
def get_analyst_data(ticker: str) -> dict:
    result = {"rec_buy": 0, "rec_hold": 0, "rec_sell": 0,
              "target_mean": None, "target_high": None, "target_low": None,
              "insider_buys": 0, "insider_sells": 0}

    # Recommendations
    rec = fh_call("recommendation_trends", ticker)
    if rec and isinstance(rec, list) and len(rec) > 0:
        r = rec[0]
        result["rec_buy"] = (r.get("buy", 0) or 0) + (r.get("strongBuy", 0) or 0)
        result["rec_hold"] = r.get("hold", 0) or 0
        result["rec_sell"] = (r.get("sell", 0) or 0) + (r.get("strongSell", 0) or 0)

    # Price target
    pt = fh_call("price_target", ticker)
    if pt and isinstance(pt, dict):
        result["target_mean"] = pt.get("targetMean")
        result["target_high"] = pt.get("targetHigh")
        result["target_low"]  = pt.get("targetLow")

    # Insider transactions (last 30 days)
    today = datetime.date.today()
    ago = today - timedelta(days=30)
    txns = fh_call("stock_insider_transactions", ticker,
                   _from=ago.strftime("%Y-%m-%d"), to=today.strftime("%Y-%m-%d"))
    if txns and isinstance(txns, dict):
        for t in txns.get("data", []):
            chg = t.get("change", 0) or 0
            if chg > 0: result["insider_buys"] += 1
            elif chg < 0: result["insider_sells"] += 1

    return result


# =====================================================================
#  6b. SECTOR RELATIVE STRENGTH
# =====================================================================
def get_relative_strength(ticker: str, period_days: int = 20) -> dict:
    """Compare ticker's return vs its sector ETF over the given period."""
    default = {"ticker_return": 0, "sector_return": 0,
               "relative_strength": 0, "outperforming": False}
    try:
        sector_etf = SECTOR_ETF_MAP.get(ticker)
        if not sector_etf:
            info = get_info(ticker)
            sector = info.get("sector", "")
            sector_etf = SECTOR_ETF_MAP.get(sector, "SPY")

        period_str = f"{period_days + 5}d"
        tk_hist = get_hist(ticker, period_str, "1d")
        se_hist = get_hist(sector_etf, period_str, "1d")

        if tk_hist.empty or se_hist.empty or len(tk_hist) < 2 or len(se_hist) < 2:
            return default

        tk_ret = (tk_hist["Close"].iloc[-1] / tk_hist["Close"].iloc[-min(period_days, len(tk_hist))] - 1) * 100
        se_ret = (se_hist["Close"].iloc[-1] / se_hist["Close"].iloc[-min(period_days, len(se_hist))] - 1) * 100
        rs = tk_ret - se_ret

        return {"ticker_return": round(tk_ret, 2), "sector_return": round(se_ret, 2),
                "relative_strength": round(rs, 2), "outperforming": rs > 0}
    except Exception:
        return default


# =====================================================================
#  7. NEWS  (yfinance + Finnhub + Google RSS, deduplicated)
# =====================================================================
def _google_news(query: str, n: int = 3) -> list[dict]:
    try:
        url = f"https://news.google.com/rss/search?q={query}+stock&hl=en-US"
        feed = feedparser.parse(url)
        out = []
        for e in feed.entries[:n]:
            out.append({"title": e.get("title", ""),
                        "link": e.get("link", ""),
                        "publisher": e.get("source", {}).get("title", "Google News")})
        return out
    except Exception:
        return []


def score_news_sentiment(ticker: str, headlines: list[str]) -> float:
    """Use Claude API to score news sentiment. Returns -1.0 to +1.0, 0.0 on failure."""
    if not ANTHROPIC_API_KEY or not headlines:
        return 0.0
    try:
        bullet_list = "\n".join(f"- {h}" for h in headlines if h)
        prompt = (f"You are a financial analyst. Rate the overall sentiment of these news "
                  f"headlines for {ticker} as a single float between -1.0 (very bearish) and "
                  f"+1.0 (very bullish). Return ONLY the number, no explanation.\n"
                  f"Headlines:\n{bullet_list}")
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 10,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=15,
        )
        if resp.status_code == 200:
            text = resp.json()["content"][0]["text"].strip()
            val = float(text)
            return max(-1.0, min(1.0, val))
    except Exception:
        pass
    return 0.0


def get_ticker_news(ticker: str) -> dict:
    """3 deduplicated headlines from yfinance, Finnhub, Google News + sentiment score."""
    all_items: list[dict] = []
    seen_titles: list[str] = []

    def _add(title, link="", pub=""):
        if not title:
            return
        for st in seen_titles:
            if _similar(title, st):
                return
        seen_titles.append(title)
        all_items.append({"title": title, "link": link, "publisher": pub})

    # yfinance
    try:
        for a in (yf.Ticker(ticker).news or [])[:3]:
            _add(a.get("title", ""), a.get("link", ""), a.get("publisher", ""))
    except Exception:
        pass

    # Finnhub
    today = datetime.date.today()
    ago = today - timedelta(days=3)
    fh_news = fh_call("company_news", ticker,
                      _from=ago.strftime("%Y-%m-%d"), to=today.strftime("%Y-%m-%d"))
    if fh_news and isinstance(fh_news, list):
        for a in fh_news[:3]:
            _add(a.get("headline", ""), a.get("url", ""), a.get("source", "Finnhub"))

    # Google News
    for a in _google_news(ticker, 3):
        _add(a["title"], a["link"], a["publisher"])

    items = all_items[:3]
    sentiment = score_news_sentiment(ticker, [i["title"] for i in items])
    return {"headlines": items, "sentiment_score": round(sentiment, 2)}


def get_macro_news() -> dict:
    """General market headlines + keyword-based risk flags."""
    headlines: list[dict] = []
    risks: list[dict] = []
    seen: list[str] = []

    def _add_hl(title, link="", pub=""):
        if not title:
            return
        for s in seen:
            if _similar(title, s):
                return
        seen.append(title)
        headlines.append({"title": title, "link": link, "publisher": pub})

    # Finnhub general news
    gen = fh_call("general_news", "general", min_id=0)
    if gen and isinstance(gen, list):
        for a in gen[:5]:
            _add_hl(a.get("headline", ""), a.get("url", ""), a.get("source", ""))

    # Google News macro
    for a in _google_news("stock market today", 5):
        _add_hl(a["title"], a["link"], a["publisher"])

    # Scan for risk keywords
    all_titles = " ".join(h["title"] for h in headlines).lower()
    portfolio_tks = [p["ticker"] for p in MY_PORTFOLIO]
    flagged: dict[str, dict] = {}
    for kw, info in MACRO_KEYWORDS.items():
        if kw in all_titles:
            tks = info["tickers"]
            if "*" in tks:
                tks = portfolio_tks
            for tk in tks:
                if tk not in flagged or info["level"] == "HIGH":
                    flagged[tk] = {"level": info["level"], "reason": info["reason"],
                                   "keyword": kw}
    for tk, data in flagged.items():
        risks.append({"ticker": tk, **data})

    return {"headlines": headlines[:8], "risks": risks}


# =====================================================================
#  8. TRADE STRATEGIES
# =====================================================================
def strategy_rsi_macd(tech: dict) -> bool:
    rsi = tech.get("rsi")
    return rsi is not None and rsi < 45 and tech.get("macd_label") == "BULLISH CROSS"

def strategy_bb_mean_reversion(tech: dict) -> bool:
    rsi = tech.get("rsi")
    return tech.get("bb_label") == "NEAR LOWER" and rsi is not None and rsi < 40

def strategy_golden_cross(tech: dict) -> bool:
    return (tech.get("ema_label") == "GOLDEN CROSS" and
            tech.get("vol_label") == "HIGH VOLUME")

def strategy_earnings_rebound(tech: dict, days_since_earnings: int | None) -> bool:
    rsi = tech.get("rsi")
    return (rsi is not None and rsi < 35 and
            days_since_earnings is not None and days_since_earnings <= 5)

def strategy_institutional(analyst: dict) -> bool:
    return analyst.get("insider_buys", 0) > 0

STRATEGY_NAMES = {
    "RSI_MACD": "RSI Momentum + MACD Cross",
    "BB_MEAN_REVERSION": "Bollinger Band Mean Reversion",
    "GOLDEN_CROSS": "EMA Golden Cross Breakout",
    "EARNINGS_REBOUND": "Earnings Dip Buy",
    "INSTITUTIONAL": "Smart Money / Institutional Accumulation",
    "MANUAL": "Manual Thesis",
}

def detect_strategy(tech: dict, analyst: dict, earnings: dict) -> str:
    if strategy_rsi_macd(tech): return "RSI_MACD"
    if strategy_bb_mean_reversion(tech): return "BB_MEAN_REVERSION"
    if strategy_golden_cross(tech): return "GOLDEN_CROSS"
    if strategy_earnings_rebound(tech, earnings.get("days_to_earnings")): return "EARNINGS_REBOUND"
    if strategy_institutional(analyst): return "INSTITUTIONAL"
    return "MANUAL"


def compute_fill_window(ticker: str, entry: float) -> str:
    try:
        df = get_hist(ticker, "5d", "5m")
        if df.empty:
            return "Entry not yet reached -- monitor open"
        hits = df[df["Low"] <= entry]
        if hits.empty:
            return "Entry not yet reached -- monitor open"
        idx = hits.index
        if hasattr(idx, "tz_convert"):
            try:
                idx = idx.tz_convert("America/New_York")
            except Exception:
                pass
        hours = idx.hour + idx.minute / 60.0
        avg = hours.mean()
        h1, m1 = int(avg), int((avg % 1) * 60)
        h2, m2 = (h1, m1 + 30) if m1 + 30 < 60 else (h1 + 1, (m1 + 30) % 60)
        return f"Typically at/below ${entry:.2f} between {h1}:{m1:02d}-{h2}:{m2:02d} EST"
    except Exception:
        return "Unable to compute fill window"


def compute_position_size(entry: float, stop: float) -> int:
    risk = entry - stop
    if risk <= 0:
        return 0
    return max(1, int(ACCOUNT_SIZE * 0.01 / risk))


# =====================================================================
#  9. SIGNAL LOGIC  (per-ticker, 2026 strategy)
# =====================================================================
def signal_logic(tk: str, price: float, pnl: float, pe: float | None,
                 day_chg: float, hi52: float | None) -> tuple[str, str]:
    dfh = (hi52 - price) / hi52 if hi52 and hi52 > 0 else None

    if tk == "OKLO":
        if price >= 85: return "SELL", "Price exceeded $85 target -- take profit"
        if pnl > 30:   return "TRIM", f"Up {pnl:+.1f}% -- take profit before Q1 volatility"
        if pnl < -20:  return "WATCH", f"Down {pnl:+.1f}% -- pre-revenue risk"
        if day_chg<-5:  return "SELL", f"Sharp {day_chg:+.1f}% drop -- protect capital"
        return "WATCH", "Hold until July 2026 DOE milestones; sell if >$85"

    if tk in ("VOO", "SCHD"):
        if tk == "VOO" and price < 615:
            return "BUY", "Below $615 threshold -- accumulate"
        if day_chg < -3: return "BUY", f"Down {day_chg:+.1f}% -- discount, accumulate"
        if day_chg < -2: return "BUY", f"Dip of {day_chg:+.1f}% -- good DCA entry"
        return "HOLD", "Long-term compounding in progress"

    if tk == "EWY":
        if dfh is not None and dfh < 0.02:
            return "TRIM", "Near 52W high -- upside capped, take 25% profit"
        if pnl > 25:    return "TRIM", f"Up {pnl:+.1f}% -- lock in international gains"
        if day_chg < -3: return "BUY", f"Down {day_chg:+.1f}% -- EM dip opportunity"
        return "HOLD", "Healthy international exposure"

    # Generic
    if day_chg < -5: return "SELL", f"Sharp {day_chg:+.1f}% drop"
    if pnl > 30 and pe and pe > 35: return "SELL", f"Up {pnl:+.1f}% w/ high PE"
    if pe and pe < 15: return "BUY", f"Deep value -- PE {pe:.1f}"
    return "HOLD", "No action needed"


# =====================================================================
#  9b. COMPOSITE SIGNAL SCORING
# =====================================================================
def compute_signal_score(ticker: str, technicals: dict, financials: dict,
                         analyst_data: dict, news: dict,
                         price: float = 0, pnl: float = 0,
                         day_chg: float = 0, hi52: float | None = None) -> dict:
    """Compute a composite score from -10 to +10 with per-component breakdown."""
    breakdown: dict[str, float] = {}
    parts: list[str] = []

    # --- Technical components ---
    rsi = technicals.get("rsi")
    if rsi is not None:
        if rsi < 30: s = 2.0
        elif rsi < 45: s = 1.0
        elif rsi <= 55: s = 0.0
        elif rsi <= 70: s = -0.5
        else: s = -2.0
        breakdown["rsi"] = s
        if s != 0: parts.append(f"RSI {rsi:.0f} ({'oversold' if s > 0 else 'overbought'})")
    else:
        breakdown["rsi"] = 0.0

    macd_lbl = technicals.get("macd_label", "NEUTRAL")
    if "BULLISH" in macd_lbl: breakdown["macd"] = 2.0; parts.append("MACD bullish crossover")
    elif "BEARISH" in macd_lbl: breakdown["macd"] = -2.0; parts.append("MACD bearish crossover")
    else: breakdown["macd"] = 0.0

    bb_lbl = technicals.get("bb_label", "N/A")
    if bb_lbl == "NEAR LOWER": breakdown["bollinger"] = 1.0; parts.append("Near lower Bollinger band")
    elif bb_lbl == "NEAR UPPER": breakdown["bollinger"] = -1.0; parts.append("Near upper Bollinger band")
    else: breakdown["bollinger"] = 0.0

    ema_lbl = technicals.get("ema_label", "N/A")
    if ema_lbl == "GOLDEN CROSS": breakdown["ema_cross"] = 1.5; parts.append("EMA golden cross")
    elif ema_lbl == "DEATH CROSS": breakdown["ema_cross"] = -1.5; parts.append("EMA death cross")
    else: breakdown["ema_cross"] = 0.0

    vol_lbl = technicals.get("vol_label", "NORMAL")
    vol_up = technicals.get("vol_up_day", True)
    if vol_lbl == "HIGH VOLUME":
        breakdown["volume"] = 0.5 if vol_up else -0.5
        parts.append(f"High volume {'up' if vol_up else 'down'} day")
    else:
        breakdown["volume"] = 0.0

    # --- Fundamental components ---
    pe = financials.get("trail_pe") or financials.get("fwd_pe")
    if pe is not None:
        if pe < 15: breakdown["pe_ratio"] = 1.0; parts.append(f"Deep value PE {pe:.1f}")
        elif pe <= 25: breakdown["pe_ratio"] = 0.0
        elif pe <= 40: breakdown["pe_ratio"] = -0.5
        else: breakdown["pe_ratio"] = -1.0; parts.append(f"High PE {pe:.1f}")
    else:
        breakdown["pe_ratio"] = 0.0

    # --- Analyst consensus ---
    buys = analyst_data.get("rec_buy", 0)
    sells = analyst_data.get("rec_sell", 0)
    if buys > sells * 2: breakdown["analyst_consensus"] = 1.0; parts.append("Strong analyst buy consensus")
    elif sells > buys: breakdown["analyst_consensus"] = -1.0; parts.append("Analyst consensus bearish")
    else: breakdown["analyst_consensus"] = 0.0

    # --- Insider activity ---
    ins_buys = analyst_data.get("insider_buys", 0)
    ins_sells = analyst_data.get("insider_sells", 0)
    if ins_buys > ins_sells: breakdown["insider_activity"] = 0.5; parts.append("Net insider buying")
    elif ins_sells > ins_buys: breakdown["insider_activity"] = -0.5; parts.append("Net insider selling")
    else: breakdown["insider_activity"] = 0.0

    # --- News sentiment ---
    sent = 0.0
    if isinstance(news, dict):
        sent = news.get("sentiment_score", 0.0)
    breakdown["news_sentiment"] = round(max(-1.0, min(1.0, sent)), 2)
    if abs(sent) > 0.3:
        parts.append(f"News sentiment {'bullish' if sent > 0 else 'bearish'} ({sent:+.2f})")

    # --- Total score ---
    raw_score = sum(breakdown.values())
    score = round(max(-10.0, min(10.0, raw_score)), 1)

    # --- Map to signal ---
    if score > 3: signal = "BUY"
    elif score > 1: signal = "TRIM"
    elif score >= -1: signal = "HOLD"
    elif score >= -3: signal = "WATCH"
    else: signal = "SELL"

    reasoning = ". ".join(parts) + "." if parts else "No strong signals detected."

    # --- Per-ticker hard caps (override score-based signal) ---
    override_reason = None
    if ticker == "OKLO":
        if price >= 85: signal = "SELL"; override_reason = "Price exceeded $85 target -- take profit"
        elif pnl > 30: signal = "TRIM"; override_reason = f"Up {pnl:+.1f}% -- take profit before Q1 volatility"
        elif pnl < -20: signal = "WATCH"; override_reason = f"Down {pnl:+.1f}% -- pre-revenue risk"
        elif day_chg < -5: signal = "SELL"; override_reason = f"Sharp {day_chg:+.1f}% drop -- protect capital"
    elif ticker in ("VOO", "SCHD"):
        if ticker == "VOO" and price < 615: signal = "BUY"; override_reason = "Below $615 threshold -- accumulate"
        elif day_chg < -3: signal = "BUY"; override_reason = f"Down {day_chg:+.1f}% -- discount, accumulate"
    elif ticker == "EWY":
        dfh = (hi52 - price) / hi52 if hi52 and hi52 > 0 else None
        if dfh is not None and dfh < 0.02: signal = "TRIM"; override_reason = "Near 52W high -- upside capped, take 25% profit"
        elif pnl > 25: signal = "TRIM"; override_reason = f"Up {pnl:+.1f}% -- lock in international gains"

    if override_reason:
        reasoning = override_reason

    return {"score": score, "signal": signal, "breakdown": breakdown, "reasoning": reasoning}


# =====================================================================
#  10. PORTFOLIO ANALYSIS
# =====================================================================
def _timeline_block(tk: str, price: float, tech: dict, earnings: dict) -> dict:
    """Generate short/medium/long-term timeline for a holding."""
    ed = earnings.get("next_earnings")
    ed_str = ed.strftime("%b %d") if ed else "TBD"
    atr_s = tech.get("atr_stop") or price * 0.95
    atr_t = tech.get("atr_target") or price * 1.10
    bb = tech.get("bb_label", "N/A")

    tl = {
        "short_level": f"Support: ${atr_s:.2f}  |  Resistance: ${atr_t:.2f}  |  BB: {bb}",
        "short_trigger": "",
        "med_catalyst": f"Next earnings: {ed_str}",
        "med_target": "",
        "long_thesis": "",
        "long_invalidate": "",
    }

    if tk == "OKLO":
        tl["short_trigger"] = "Sell if price breaks below $55 or drops >5% in a day"
        tl["med_target"] = "Trim at $82-$85 range (analyst consensus)"
        tl["long_thesis"] = "Nuclear micro-reactor play -- DOE milestones in 2027"
        tl["long_invalidate"] = "Miss July 2026 DOE criticality deadline"
    elif tk == "VOO":
        tl["short_trigger"] = "Buy more if price dips below $615"
        tl["med_target"] = "S&P target ~7,000 by Q3 2026"
        tl["long_thesis"] = "Core index -- long-term compounding"
        tl["long_invalidate"] = "Only sell in cash emergency"
    elif tk == "SCHD":
        tl["short_trigger"] = "Accumulate on any >2% weekly dip"
        tl["med_target"] = "Value rotation expected in H2 2026"
        tl["long_thesis"] = "Dividend growth + value factor play"
        tl["long_invalidate"] = "Dividend cut or major sector rotation away from value"
    elif tk == "EWY":
        tl["short_trigger"] = "Trim 25% now -- near 52W high with tariff headwinds"
        tl["med_target"] = "Re-enter on a 10%+ pullback"
        tl["long_thesis"] = "South Korea EM diversification"
        tl["long_invalidate"] = "New tariffs >15% or China-Taiwan escalation"
    else:
        tl["short_trigger"] = f"Stop loss at ${atr_s:.2f} (ATR-based)"
        tl["med_target"] = f"Target ${atr_t:.2f}"
        tl["long_thesis"] = "Monitor fundamentals quarterly"
        tl["long_invalidate"] = "Thesis break if PE > 40 or revenue declines 2 quarters"
    return tl


def _action_text(signal: str, h: dict) -> str:
    today30 = (datetime.date.today() + timedelta(days=30)).strftime("%B %d, %Y")
    if signal == "HOLD":
        return f"Thesis intact. Next review: {today30}"
    if signal == "TRIM":
        n = max(1, int(h["shares"] * 0.25))
        return f"Sell {n} shares. Suggested limit: ${h['current_price']:.2f}"
    if signal == "SELL":
        return f"Exit full position. Target exit: ${h['current_price']:.2f}"
    if signal == "BUY":
        risk = ACCOUNT_SIZE * 0.01
        n = max(1, int(risk / (h["current_price"] * 0.02)))
        return f"Add {n} shares. Limit order at: ${h['current_price'] * 0.995:.2f}"
    if signal == "WATCH":
        return f"Monitor closely. Next review: {today30}"
    return f"Next review: {today30}"


def analyse_portfolio(portfolio: list[dict]) -> list[dict]:
    results = []
    for pos in portfolio:
        tk, shares, avg = pos["ticker"], pos["shares"], pos["avg_cost"]
        info = get_info(tk)
        cur = info.get("currentPrice") or info.get("regularMarketPrice") or 0
        prev = info.get("previousClose") or info.get("regularMarketPreviousClose") or 0
        pe = info.get("trailingPE") or info.get("forwardPE")
        name = info.get("shortName") or info.get("longName") or tk
        hi52 = info.get("fiftyTwoWeekHigh")
        lo52 = info.get("fiftyTwoWeekLow")
        mcap_r = info.get("marketCap")

        tc = shares * avg; mv = shares * cur
        opnl = mv - tc; opnl_p = (cur - avg) / avg * 100 if avg else 0
        dpnl = (cur - prev) * shares if prev else 0
        dpnl_p = (cur - prev) / prev * 100 if prev else 0
        rng = (cur - lo52) / (hi52 - lo52) * 100 if hi52 and lo52 and hi52 != lo52 else None

        if mcap_r and mcap_r >= 1e12: mcap = f"${mcap_r/1e12:.2f}T"
        elif mcap_r and mcap_r >= 1e9: mcap = f"${mcap_r/1e9:.2f}B"
        elif mcap_r and mcap_r >= 1e6: mcap = f"${mcap_r/1e6:.1f}M"
        else: mcap = "N/A"

        tech = compute_technicals(tk)
        fins = get_financials(tk)
        earn = get_earnings_info(tk)
        anly = get_analyst_data(tk)
        news = get_ticker_news(tk)
        rel_str = get_relative_strength(tk)

        scoring = compute_signal_score(
            tk, tech, fins, anly, news,
            price=cur, pnl=opnl_p, day_chg=dpnl_p, hi52=hi52)
        sig = scoring["signal"]
        reason = scoring["reasoning"]

        timeline = _timeline_block(tk, cur, tech, earn)
        action = _action_text(sig, {"shares": shares, "current_price": cur})

        results.append({
            "ticker": tk, "name": name, "shares": shares, "avg_cost": avg,
            "current_price": round(cur, 2), "prev_close": round(prev, 2),
            "total_cost": round(tc, 2), "market_value": round(mv, 2),
            "open_pnl": round(opnl, 2), "open_pnl_pct": round(opnl_p, 2),
            "day_pnl": round(dpnl, 2), "day_pnl_pct": round(dpnl_p, 2),
            "pe": round(pe, 2) if pe else None, "market_cap": mcap,
            "hi52": round(hi52, 2) if hi52 else None,
            "lo52": round(lo52, 2) if lo52 else None,
            "range_pct": round(rng, 1) if rng is not None else None,
            "signal": sig, "reason": reason, "action": action,
            "score": scoring["score"], "score_breakdown": scoring["breakdown"],
            "strategy": PORTFOLIO_STRATEGIES.get(tk, ""),
            "tech": tech, "fins": fins, "earn": earn, "analyst": anly,
            "news": news, "timeline": timeline,
            "relative_strength": rel_str,
        })
        print(f"  [PORT] {tk:6s}  ${cur:>8.2f}  P&L {opnl_p:+.2f}%  -> {sig} (score {scoring['score']:+.1f})")
    return results


# =====================================================================
#  11. SMART PICK ENRICHMENT
# =====================================================================
def enrich_picks(picks: list[dict]) -> list[dict]:
    out = []
    for p in picks:
        tk = p["ticker"]
        info = get_info(tk)
        cur = info.get("currentPrice") or info.get("regularMarketPrice") or 0
        prev = info.get("previousClose") or info.get("regularMarketPreviousClose") or 0
        day_chg = (cur - prev) / prev * 100 if prev else 0

        tech = compute_technicals(tk)
        earn = get_earnings_info(tk)
        anly = get_analyst_data(tk)
        news = get_ticker_news(tk)
        fins = get_financials(tk)

        scoring = compute_signal_score(tk, tech, fins, anly, news, price=cur, day_chg=day_chg)

        # Strategy detection (prefer label from config, auto-detect if MANUAL)
        strat = p.get("strategy_type", "MANUAL")
        auto = detect_strategy(tech, anly, earn)
        if strat == "MANUAL" and auto != "MANUAL":
            strat = auto

        # ATR-dynamic levels
        entry = p["entry"]; target = p["target"]; stop = p["stop"]
        if tech.get("atr_stop") and tech.get("atr_target"):
            stop = tech["atr_stop"]
            target = tech["atr_target"]

        risk_pct = (entry - stop) / entry * 100 if entry else 0
        reward_pct = (target - entry) / entry * 100 if entry else 0
        rr = reward_pct / risk_pct if risk_pct > 0 else 0
        pos_size = compute_position_size(entry, stop)
        fill = compute_fill_window(tk, entry)

        status = "ACTIVE" if cur and cur <= entry * 1.02 else "WATCH"

        out.append({
            **p, "current_price": round(cur, 2), "day_chg": round(day_chg, 2),
            "status": status, "strategy_key": strat,
            "strategy_name": STRATEGY_NAMES.get(strat, strat),
            "entry": round(entry, 2), "target": round(target, 2),
            "stop": round(stop, 2),
            "risk_pct": round(risk_pct, 2), "reward_pct": round(reward_pct, 2),
            "rr": round(rr, 1), "pos_size": pos_size, "fill_window": fill,
            "tech": tech, "earn": earn, "analyst": anly, "news": news, "fins": fins,
            "score": scoring["score"], "score_breakdown": scoring["breakdown"],
        })
        print(f"  [PICK] {tk:6s}  ${cur:>8.2f}  Day {day_chg:+.2f}%  -> {status}  [{strat}] (score {scoring['score']:+.1f})")
    return out


# =====================================================================
#  12. S&P 500 SCAN + MARKET SUMMARY
# =====================================================================
def fetch_sp500_tickers() -> list[str]:
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    resp.raise_for_status()
    tks = pd.read_html(io.StringIO(resp.text), flavor="html5lib")[0]["Symbol"]
    tks = tks.str.replace(".", "-", regex=False).tolist()
    print(f"  [OK] Fetched {len(tks)} S&P 500 tickers.")
    return tks


def analyse_stocks(tickers: list[str]) -> pd.DataFrame:
    recs = []
    total = len(tickers)
    for i, tk in enumerate(tickers, 1):
        try:
            info = get_info(tk)
            prev = info.get("previousClose") or info.get("regularMarketPreviousClose")
            cur = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("navPrice")
            if prev and cur and prev > 0:
                recs.append({"Ticker": tk, "Previous Close": round(prev, 2),
                             "Current Price": round(cur, 2),
                             "Change %": round((cur - prev) / prev * 100, 2)})
        except Exception:
            pass
        if i % 50 == 0 or i == total:
            print(f"       Processed {i}/{total}")
    df = pd.DataFrame(recs).sort_values("Change %", ascending=False).reset_index(drop=True)
    print(f"  [OK] Analysed {len(df)} stocks.")
    return df


def get_top_movers(df, n=10):
    return df.head(n).copy(), df.tail(n).sort_values("Change %", ascending=True).copy()


def fetch_market_summary() -> dict:
    info = get_info("^GSPC")
    cur = info.get("regularMarketPrice") or info.get("previousClose") or 0
    prev = info.get("regularMarketPreviousClose") or info.get("previousClose") or 0
    chg = (cur - prev) / prev * 100 if prev else 0
    # SPY RSI
    spy_tech = compute_technicals("SPY")
    rsi = spy_tech.get("rsi")
    if rsi and rsi > 60: spy_mood = "Bullish"
    elif rsi and rsi < 40: spy_mood = "Bearish"
    else: spy_mood = "Neutral"
    return {"price": round(cur, 2), "change": round(chg, 2),
            "spy_rsi": rsi, "spy_mood": spy_mood}


# =====================================================================
#  13. RISK DASHBOARD
# =====================================================================
def compute_risk_dashboard(holdings: list[dict]) -> dict:
    total_val = sum(h["market_value"] for h in holdings)
    if total_val == 0:
        return {"weighted_beta": 0, "risk_rating": "N/A", "var_95": 0,
                "sectors": {}, "positions": []}
    w_beta = 0; sectors: dict[str, float] = {}
    daily_rets_list = []

    for h in holdings:
        w = h["market_value"] / total_val
        beta = h["fins"].get("beta") or 1.0
        w_beta += w * beta
        sec = h["fins"].get("sector", "Unknown")
        sectors[sec] = sectors.get(sec, 0) + w * 100

        # Daily returns for VaR
        hist = get_hist(h["ticker"], "30d", "1d")
        if not hist.empty and len(hist) > 1:
            rets = hist["Close"].pct_change().dropna().values
            daily_rets_list.append((w, rets))

    # Overall risk rating
    if w_beta < 0.8: rating = "LOW"
    elif w_beta < 1.2: rating = "MEDIUM"
    else: rating = "HIGH"

    # 1-day 95% VaR
    var_95 = 0
    if daily_rets_list:
        min_len = min(len(r) for _, r in daily_rets_list)
        if min_len > 0:
            port_rets = np.zeros(min_len)
            for w, r in daily_rets_list:
                port_rets += w * r[:min_len]
            var_95 = abs(np.percentile(port_rets, 5)) * total_val

    # Per-position single-day risk
    pos_risks = []
    for h in holdings:
        beta = h["fins"].get("beta") or 1.0
        risk_1d = beta * 0.02 * h["market_value"]
        pos_risks.append({"ticker": h["ticker"], "weight": round(h["market_value"]/total_val*100, 1),
                          "beta": round(beta, 2), "risk_1d": round(risk_1d, 2)})

    return {"weighted_beta": round(w_beta, 2), "risk_rating": rating,
            "var_95": round(var_95, 2), "sectors": sectors, "positions": pos_risks}


# =====================================================================
#  14. HTML BUILDERS  (dark theme, inline styles for Gmail)
# =====================================================================
C_BG     = "#0b0e11"; C_CARD   = "#141821"; C_ALT    = "#1a1f2b"
C_BORDER = "#1e2533"; C_TEXT   = "#d1d4dc"; C_DIM    = "#6b7280"
C_GREEN  = "#00d26a"; C_RED    = "#f6465d"; C_AMBER  = "#f0b90b"
C_BLUE   = "#3b82f6"; C_WHITE  = "#ffffff"; C_PURPLE = "#a78bfa"
C_CYAN   = "#22d3ee"


def _dlr(v): return f"${v:,.2f}"
def _pct_val(v):
    c = C_GREEN if v >= 0 else C_RED; s = "+" if v >= 0 else ""; a = "^" if v >= 0 else "v"
    return (f'<span style="display:inline-block;padding:2px 8px;border-radius:4px;'
            f'background:{c}1a;color:{c};font-weight:700;font-size:11px;">'
            f'{a} {s}{v:.2f}%</span>')
def _clr(v): return C_GREEN if v >= 0 else C_RED
def _sig(s):
    if "BUY" in s.upper(): bg,c = C_GREEN+"1a", C_GREEN
    elif "SELL" in s.upper(): bg,c = C_RED+"1a", C_RED
    elif "TRIM" in s.upper(): bg,c = C_AMBER+"1a", C_AMBER
    elif "WATCH" in s.upper(): bg,c = C_AMBER+"1a", C_AMBER
    elif "ERROR" in s.upper(): bg,c = C_RED+"1a", C_RED
    else: bg,c = C_TEXT+"1a", C_TEXT
    return (f'<span style="display:inline-block;padding:3px 12px;border-radius:4px;'
            f'background:{bg};color:{c};font-weight:700;font-size:11px;">{s}</span>')
def _th(t):
    return (f'<th style="padding:8px 12px;text-align:left;color:{C_DIM};font-size:9px;'
            f'font-weight:600;text-transform:uppercase;letter-spacing:0.8px;'
            f'border-bottom:2px solid {C_BORDER};">{t}</th>')
def _td(content, **kw):
    color = kw.get("color", C_TEXT); bold = "700" if kw.get("bold") else "400"
    sz = kw.get("size", "12px")
    return (f'<td style="padding:9px 12px;color:{color};font-weight:{bold};font-size:{sz};'
            f'border-bottom:1px solid {C_BORDER};">{content}</td>')
def _sec(title, body):
    return (f'<div style="margin:18px 20px;"><div style="margin-bottom:12px;padding-bottom:7px;'
            f'border-bottom:1px solid {C_BORDER};"><span style="font-size:14px;font-weight:700;'
            f'color:{C_WHITE};letter-spacing:0.3px;">{title}</span></div>{body}</div>')
def _card(body):
    return (f'<div style="background:{C_CARD};border:1px solid {C_BORDER};border-radius:8px;'
            f'padding:14px 16px;margin-bottom:10px;">{body}</div>')
def _risk_badge(level):
    c = C_RED if level=="HIGH" else C_AMBER if level=="MEDIUM" else C_GREEN
    return (f'<span style="padding:2px 8px;border-radius:3px;background:{c}1a;'
            f'color:{c};font-weight:700;font-size:10px;">{level}</span>')


def _score_breakdown_html(h: dict) -> str:
    """Compact score breakdown table for email cards."""
    bd = h.get("score_breakdown", {})
    sc = h.get("score", 0)
    if not bd:
        return ""
    sc_c = C_GREEN if sc > 1 else C_RED if sc < -1 else C_AMBER
    rows = ""
    for comp, val in bd.items():
        if val == 0:
            continue
        vc = C_GREEN if val > 0 else C_RED
        label = comp.replace("_", " ").title()
        rows += (f'<tr><td style="padding:2px 6px;color:{C_TEXT};font-size:10px;'
                 f'border-bottom:1px solid {C_BORDER};">{label}</td>'
                 f'<td style="padding:2px 6px;color:{vc};font-size:10px;font-weight:700;'
                 f'text-align:right;border-bottom:1px solid {C_BORDER};">{val:+.1f}</td></tr>')
    if not rows:
        return ""
    return (f'<div style="margin-top:8px;padding:8px 10px;background:{C_ALT};border-radius:5px;">'
            f'<div style="font-size:9px;color:{C_DIM};text-transform:uppercase;margin-bottom:4px;">'
            f'Score: <span style="color:{sc_c};font-weight:700;">{sc:+.1f}</span></div>'
            f'<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">'
            f'{rows}</table></div>')


def _relative_strength_html(h: dict) -> str:
    """Relative strength vs sector for email cards."""
    rs = h.get("relative_strength", {})
    if not rs or not isinstance(rs, dict):
        return ""
    val = rs.get("relative_strength", 0)
    out = rs.get("outperforming", False)
    c = C_GREEN if out else C_RED
    arrow = "+" if out else ""
    return (f'<div style="margin-top:4px;font-size:10px;color:{c};font-weight:600;">'
            f'vs Sector: {arrow}{val:.1f}% {"UP" if out else "DOWN"}</div>')


def get_premarket_movers(portfolio: list[dict], watchlist: list[str]) -> list[dict]:
    """Fetch pre-market price changes for portfolio + watchlist tickers."""
    movers = []
    try:
        all_tks = set(watchlist)
        for p in portfolio:
            all_tks.add(p["ticker"])
        for tk in sorted(all_tks):
            info = get_info(tk)
            pre = info.get("preMarketPrice")
            prev = info.get("previousClose") or info.get("regularMarketPreviousClose")
            if pre and prev and prev > 0:
                chg = (pre - prev) / prev * 100
                if abs(chg) > 2:
                    movers.append({"ticker": tk, "pre_price": round(pre, 2),
                                   "prev_close": round(prev, 2), "change_pct": round(chg, 2)})
    except Exception:
        pass
    return sorted(movers, key=lambda x: abs(x["change_pct"]), reverse=True)


def html_premarket(movers: list[dict]) -> str:
    """Pre-market movers section for email."""
    if not movers:
        return ""
    rows = ""
    for m in movers:
        c = C_GREEN if m["change_pct"] > 0 else C_RED
        rows += (f'<tr><td style="padding:6px 10px;color:{C_WHITE};font-weight:700;font-size:12px;'
                 f'border-bottom:1px solid {C_BORDER};">{m["ticker"]}</td>'
                 f'<td style="padding:6px 10px;color:{C_TEXT};font-size:12px;'
                 f'border-bottom:1px solid {C_BORDER};">{_dlr(m["prev_close"])}</td>'
                 f'<td style="padding:6px 10px;color:{c};font-weight:700;font-size:12px;'
                 f'border-bottom:1px solid {C_BORDER};">{_dlr(m["pre_price"])}</td>'
                 f'<td style="padding:6px 10px;border-bottom:1px solid {C_BORDER};">'
                 f'{_pct_val(m["change_pct"])}</td></tr>')
    table = (f'<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">'
             f'<thead><tr style="background:{C_CARD};">{_th("Ticker")}{_th("Prev Close")}'
             f'{_th("Pre-Market")}{_th("Change")}</tr></thead><tbody>{rows}</tbody></table>')
    return _sec("Pre-Market Movers (>2%)", table)


def html_friday_recap(holdings: list[dict]) -> str:
    """Weekly recap section for Friday emails."""
    if datetime.date.today().weekday() != 4:
        return ""
    rows = ""
    spy_hist = get_hist("SPY", "10d", "1d")
    spy_7d = 0
    if not spy_hist.empty and len(spy_hist) >= 5:
        spy_7d = (spy_hist["Close"].iloc[-1] / spy_hist["Close"].iloc[0] - 1) * 100

    best_tk, best_ret = "", -999
    worst_tk, worst_ret = "", 999

    for h in holdings:
        tk = h["ticker"]
        hist = get_hist(tk, "10d", "1d")
        if hist.empty or len(hist) < 2:
            continue
        ret = (hist["Close"].iloc[-1] / hist["Close"].iloc[0] - 1) * 100
        c = C_GREEN if ret > 0 else C_RED
        vs_spy = ret - spy_7d
        vs_c = C_GREEN if vs_spy > 0 else C_RED
        rows += (f'<tr><td style="padding:6px 10px;color:{C_WHITE};font-weight:700;'
                 f'border-bottom:1px solid {C_BORDER};">{tk}</td>'
                 f'<td style="padding:6px 10px;color:{c};font-weight:700;'
                 f'border-bottom:1px solid {C_BORDER};">{ret:+.2f}%</td>'
                 f'<td style="padding:6px 10px;color:{vs_c};font-weight:700;'
                 f'border-bottom:1px solid {C_BORDER};">{vs_spy:+.2f}%</td></tr>')
        if ret > best_ret: best_ret, best_tk = ret, tk
        if ret < worst_ret: worst_ret, worst_tk = ret, tk

    if not rows:
        return ""
    summary = (f'<div style="margin-bottom:10px;font-size:11px;color:{C_TEXT};line-height:1.6;">'
               f'SPY 7-Day: <span style="color:{C_GREEN if spy_7d > 0 else C_RED};font-weight:700;">{spy_7d:+.2f}%</span>'
               f' | Best: <span style="color:{C_GREEN};font-weight:700;">{best_tk} ({best_ret:+.2f}%)</span>'
               f' | Worst: <span style="color:{C_RED};font-weight:700;">{worst_tk} ({worst_ret:+.2f}%)</span></div>')
    table = (f'<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">'
             f'<thead><tr style="background:{C_CARD};">{_th("Ticker")}{_th("7-Day Return")}'
             f'{_th("vs SPY")}</tr></thead><tbody>{rows}</tbody></table>')
    return _sec("Weekly Recap", summary + table)


def html_header(sp, today_str, now_str):
    mood_c = C_GREEN if sp["spy_mood"]=="Bullish" else C_RED if sp["spy_mood"]=="Bearish" else C_AMBER
    return f"""
    <div style="background:linear-gradient(135deg,#141821,#1a2332);border-radius:12px 12px 0 0;
                padding:24px 20px;border-bottom:2px solid {C_AMBER};">
      <table width="100%" cellpadding="0" cellspacing="0"><tr>
        <td><div style="font-size:19px;font-weight:800;color:{C_WHITE};">AI Stock Analyst</div>
            <div style="font-size:10px;color:{C_DIM};margin-top:2px;">DAILY MARKET REPORT</div></td>
        <td style="text-align:right;">
            <div style="font-size:12px;color:{C_TEXT};font-weight:600;">{today_str}</div>
            <div style="font-size:10px;color:{C_DIM};">Generated at {now_str}</div></td>
      </tr></table>
      <div style="margin-top:12px;padding-top:10px;border-top:1px solid {C_BORDER};">
        <span style="color:{C_DIM};font-size:10px;">S&amp;P 500</span>
        <span style="color:{C_WHITE};font-weight:700;font-size:15px;margin-left:6px;">{_dlr(sp['price'])}</span>
        &ensp;{_pct_val(sp['change'])}
        <span style="margin-left:16px;color:{C_DIM};font-size:10px;">SPY RSI</span>
        <span style="color:{mood_c};font-weight:700;font-size:12px;margin-left:4px;">{sp['spy_mood']}</span>
        <span style="color:{C_DIM};font-size:10px;margin-left:2px;">({sp['spy_rsi']:.0f})</span>
      </div>
    </div>"""


def html_macro(macro):
    rows = ""
    for h in macro["headlines"][:6]:
        pub = f' <span style="color:{C_DIM};">-- {h["publisher"]}</span>' if h["publisher"] else ""
        lnk = f'<a href="{h["link"]}" style="color:{C_BLUE};text-decoration:none;">' if h["link"] else ""
        cls = "</a>" if h["link"] else ""
        rows += f'<div style="padding:4px 0;border-bottom:1px solid {C_BORDER};font-size:11px;color:{C_TEXT};">{lnk}{h["title"]}{cls}{pub}</div>'
    risk_rows = ""
    if macro["risks"]:
        for r in macro["risks"]:
            risk_rows += f'<tr><td style="padding:6px 10px;color:{C_WHITE};font-weight:600;font-size:12px;border-bottom:1px solid {C_BORDER};">{r["ticker"]}</td><td style="padding:6px 10px;border-bottom:1px solid {C_BORDER};">{_risk_badge(r["level"])}</td><td style="padding:6px 10px;color:{C_TEXT};font-size:11px;border-bottom:1px solid {C_BORDER};">{r["reason"]} (keyword: {r["keyword"]})</td></tr>'
        risk_rows = f'<div style="margin-top:10px;"><div style="font-size:9px;color:{C_DIM};text-transform:uppercase;letter-spacing:0.8px;margin-bottom:4px;">Portfolio Risk Flags</div><table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;"><thead><tr>{_th("Ticker")}{_th("Risk")}{_th("Reason")}</tr></thead><tbody>{risk_rows}</tbody></table></div>'
    return _sec("Macro & Political Risk", rows + risk_rows)


def html_catalysts(cats):
    if not cats:
        return _sec("This Week's Catalysts", f'<div style="color:{C_DIM};font-size:11px;">No major earnings this week for your watchlist.</div>')
    rows = ""
    for c in cats:
        d = c["date"].strftime("%b %d") if c["date"] else "TBD"
        eps = f"est EPS: ${c['eps_est']:.2f}" if c["eps_est"] else "est EPS: N/A"
        clr = C_AMBER if c["days"] <= 3 else C_TEXT
        rows += f'<div style="padding:5px 0;border-bottom:1px solid {C_BORDER};font-size:12px;"><span style="color:{C_WHITE};font-weight:700;">{c["ticker"]}</span> <span style="color:{clr};"> -- reports {d} ({eps})</span></div>'
    return _sec("This Week's Catalysts", rows)


def html_portfolio(holdings):
    if not holdings: return ""
    tv = sum(h["market_value"] for h in holdings)
    tc = sum(h["total_cost"] for h in holdings)
    tp = tv - tc; tpct = tp/tc*100 if tc else 0; td = sum(h["day_pnl"] for h in holdings)
    summary = f'''<div style="background:{C_ALT};border-radius:8px;padding:14px 16px;margin-bottom:14px;border:1px solid {C_BORDER};">
      <table width="100%" cellpadding="0" cellspacing="0"><tr>
        <td style="text-align:center;width:25%;"><div style="font-size:9px;color:{C_DIM};text-transform:uppercase;letter-spacing:0.8px;">Total Value</div><div style="font-size:16px;font-weight:700;color:{C_WHITE};">{_dlr(tv)}</div></td>
        <td style="text-align:center;width:25%;border-left:1px solid {C_BORDER};"><div style="font-size:9px;color:{C_DIM};text-transform:uppercase;letter-spacing:0.8px;">Total Cost</div><div style="font-size:16px;font-weight:700;color:{C_TEXT};">{_dlr(tc)}</div></td>
        <td style="text-align:center;width:25%;border-left:1px solid {C_BORDER};"><div style="font-size:9px;color:{C_DIM};text-transform:uppercase;letter-spacing:0.8px;">Open P&amp;L</div><div style="font-size:16px;font-weight:700;color:{_clr(tp)};"> {"+" if tp>=0 else ""}{_dlr(tp)}</div>{_pct_val(tpct)}</td>
        <td style="text-align:center;width:25%;border-left:1px solid {C_BORDER};"><div style="font-size:9px;color:{C_DIM};text-transform:uppercase;letter-spacing:0.8px;">Today</div><div style="font-size:16px;font-weight:700;color:{_clr(td)};">{"+" if td>=0 else ""}{_dlr(td)}</div></td>
      </tr></table></div>'''

    cards = ""
    for h in holdings:
        t = h["tech"]; e = h["earn"]; a = h["analyst"]; tl = h["timeline"]
        pe_s = f'{h["pe"]:.1f}' if h["pe"] else "N/A"
        rsi_s = f'{t["rsi"]:.0f} ({t["rsi_label"]})' if t["rsi"] else "N/A"
        earn_s = ""
        if e.get("days_to_earnings") is not None:
            ec = C_AMBER if e["days_to_earnings"] <= 7 else C_DIM
            earn_s = f'<span style="color:{ec};">Earnings in {e["days_to_earnings"]}d ({e["next_earnings"].strftime("%b %d") if e["next_earnings"] else "TBD"})</span>'
        if e.get("last_eps_actual") is not None:
            earn_s += f' | Last Q: ${e["last_eps_actual"]:.2f} vs ${e["last_eps_est"]:.2f}' if e.get("last_eps_est") else ""
            if e.get("last_surprise_pct") is not None:
                sc = C_GREEN if e["last_surprise_pct"] >= 0 else C_RED
                earn_s += f' (<span style="color:{sc};">{e["last_surprise_pct"]:+.1f}%</span>)'
        analyst_s = f'{a["rec_buy"]} Buy | {a["rec_hold"]} Hold | {a["rec_sell"]} Sell'
        tgt_s = ""
        if a["target_mean"]:
            tgt_s = f'Target: ${a["target_low"]:.0f} / ${a["target_mean"]:.0f} / ${a["target_high"]:.0f}'
        insider_s = f'Insider: {a["insider_buys"]} buys / {a["insider_sells"]} sells (30d)'
        news_data = h.get("news", {})
        news_items = news_data.get("headlines", []) if isinstance(news_data, dict) else news_data
        sent_score = news_data.get("sentiment_score", 0) if isinstance(news_data, dict) else 0
        sent_c = C_GREEN if sent_score > 0.3 else C_RED if sent_score < -0.3 else C_DIM
        sent_lbl = "Bullish" if sent_score > 0.3 else "Bearish" if sent_score < -0.3 else "Neutral"
        news_h = f'<div style="padding:3px 0;font-size:10px;"><span style="color:{sent_c};font-weight:700;">News Sentiment: {sent_lbl} ({sent_score:+.2f})</span></div>'
        for n in news_items[:3]:
            lnk = f'<a href="{n["link"]}" style="color:{C_BLUE};text-decoration:none;">' if n["link"] else ""
            cl = "</a>" if n["link"] else ""
            news_h += f'<div style="padding:3px 0;font-size:10px;color:{C_TEXT};border-bottom:1px solid {C_BORDER};">{lnk}{n["title"]}{cl}</div>'

        cards += f'''<div style="background:{C_CARD};border:1px solid {C_BORDER};border-radius:8px;padding:16px;margin-bottom:12px;">
          <table width="100%" cellpadding="0" cellspacing="0"><tr>
            <td><span style="font-size:16px;font-weight:800;color:{C_WHITE};">{h["ticker"]}</span>
                <span style="font-size:11px;color:{C_DIM};margin-left:6px;">{h["name"]}</span></td>
            <td style="text-align:right;">{_sig(h["signal"])}</td></tr></table>
          <div style="font-size:10px;color:{C_DIM};margin-top:4px;font-style:italic;">{h["reason"]}</div>
          <div style="font-size:11px;color:{C_AMBER};margin-top:3px;font-weight:600;">Action: {h["action"]}</div>
          <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:10px;"><tr>
            <td style="width:14%;padding:4px;"><div style="font-size:8px;color:{C_DIM};text-transform:uppercase;">Price</div><div style="font-size:13px;font-weight:700;color:{C_WHITE};">{_dlr(h["current_price"])}</div></td>
            <td style="width:14%;padding:4px;"><div style="font-size:8px;color:{C_DIM};text-transform:uppercase;">Avg Cost</div><div style="font-size:13px;font-weight:700;color:{C_TEXT};">{_dlr(h["avg_cost"])}</div></td>
            <td style="width:10%;padding:4px;"><div style="font-size:8px;color:{C_DIM};text-transform:uppercase;">Shares</div><div style="font-size:13px;font-weight:700;color:{C_WHITE};">{h["shares"]}</div></td>
            <td style="width:10%;padding:4px;"><div style="font-size:8px;color:{C_DIM};text-transform:uppercase;">PE</div><div style="font-size:13px;font-weight:700;color:{C_AMBER};">{pe_s}</div></td>
            <td style="width:14%;padding:4px;"><div style="font-size:8px;color:{C_DIM};text-transform:uppercase;">RSI</div><div style="font-size:13px;font-weight:700;color:{C_WHITE};">{rsi_s}</div></td>
            <td style="width:14%;padding:4px;"><div style="font-size:8px;color:{C_DIM};text-transform:uppercase;">Open P&L</div><div style="font-size:13px;font-weight:700;color:{_clr(h["open_pnl"])};">{"+" if h["open_pnl"]>=0 else ""}{_dlr(h["open_pnl"])}</div>{_pct_val(h["open_pnl_pct"])}</td>
            <td style="width:14%;padding:4px;"><div style="font-size:8px;color:{C_DIM};text-transform:uppercase;">Day P&L</div><div style="font-size:13px;font-weight:700;color:{_clr(h["day_pnl"])};">{"+" if h["day_pnl"]>=0 else ""}{_dlr(h["day_pnl"])}</div>{_pct_val(h["day_pnl_pct"])}</td>
          </tr></table>
          <div style="margin-top:8px;padding:8px 10px;background:{C_ALT};border-radius:5px;font-size:10px;color:{C_TEXT};line-height:1.6;">
            {earn_s}<br>Analyst: {analyst_s} {tgt_s}<br>{insider_s}
          </div>
          {_score_breakdown_html(h)}
          {_relative_strength_html(h)}
          <div style="margin-top:8px;padding:8px 10px;background:{C_ALT};border-radius:5px;font-size:10px;line-height:1.6;">
            <div style="color:{C_CYAN};font-weight:600;">Short-term (0-30d):</div><div style="color:{C_TEXT};">{tl["short_level"]}<br>{tl["short_trigger"]}</div>
            <div style="color:{C_CYAN};font-weight:600;margin-top:4px;">Medium-term (1-6mo):</div><div style="color:{C_TEXT};">{tl["med_catalyst"]}<br>{tl["med_target"]}</div>
            <div style="color:{C_CYAN};font-weight:600;margin-top:4px;">Long-term (6-24mo):</div><div style="color:{C_TEXT};">{tl["long_thesis"]}<br>Invalidate: {tl["long_invalidate"]}</div>
          </div>
          {f'<div style="margin-top:6px;">{news_h}</div>' if news_h else ""}
        </div>'''
    return _sec("Your Portfolio", summary + cards)


def html_picks(picks, title):
    if not picks:
        return _sec(title, f'<div style="color:{C_DIM};font-size:11px;">No picks today.</div>')
    cards = ""
    for p in picks:
        st_clr = C_GREEN if p["status"] == "ACTIVE" else C_AMBER
        t = p.get("tech", {})
        rsi_s = f'RSI {t["rsi"]:.0f}' if t.get("rsi") else ""
        macd_s = t.get("macd_label", "")
        ema_s = t.get("ema_label", "")
        earn_s = ""
        if p.get("earn", {}).get("days_to_earnings") is not None:
            d = p["earn"]["days_to_earnings"]
            earn_s = f'Earnings in {d}d' if d >= 0 else ""
        p_news = p.get("news", {})
        p_news_items = p_news.get("headlines", []) if isinstance(p_news, dict) else p_news
        news_h = ""
        for n in p_news_items[:2]:
            lnk = f'<a href="{n["link"]}" style="color:{C_BLUE};text-decoration:none;">' if n["link"] else ""
            cl = "</a>" if n["link"] else ""
            news_h += f'<div style="padding:2px 0;font-size:10px;color:{C_TEXT};">{lnk}{n["title"]}{cl}</div>'

        cards += f'''<div style="background:{C_CARD};border:1px solid {C_BORDER};border-radius:8px;padding:14px 16px;margin-bottom:10px;">
          <table width="100%" cellpadding="0" cellspacing="0"><tr>
            <td><span style="font-size:15px;font-weight:700;color:{C_WHITE};">{p["ticker"]}</span>
                <span style="font-size:11px;color:{C_DIM};margin-left:6px;">{p["name"]}</span></td>
            <td style="text-align:right;">
              <span style="font-size:13px;font-weight:700;color:{C_WHITE};">{_dlr(p["current_price"])}</span>
              &ensp;{_pct_val(p["day_chg"])}
              <span style="font-size:9px;font-weight:700;color:{st_clr};padding:2px 6px;border-radius:3px;background:{st_clr}1a;margin-left:6px;">{p["status"]}</span>
            </td></tr></table>
          <div style="margin-top:6px;padding:6px 10px;background:{C_PURPLE}15;border-radius:4px;font-size:11px;color:{C_PURPLE};font-weight:600;">
            Strategy: {p["strategy_name"]}</div>
          <div style="font-size:11px;color:{C_TEXT};margin-top:6px;line-height:1.5;">{p["reason"]}</div>
          <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:8px;background:{C_ALT};border-radius:5px;">
            <tr>
              <td style="padding:7px 12px;text-align:center;width:20%;"><div style="font-size:8px;color:{C_DIM};text-transform:uppercase;">Entry</div><div style="font-size:13px;font-weight:700;color:{C_BLUE};">{_dlr(p["entry"])}</div></td>
              <td style="padding:7px 12px;text-align:center;width:20%;border-left:1px solid {C_BORDER};"><div style="font-size:8px;color:{C_DIM};text-transform:uppercase;">Target</div><div style="font-size:13px;font-weight:700;color:{C_GREEN};">{_dlr(p["target"])}</div></td>
              <td style="padding:7px 12px;text-align:center;width:20%;border-left:1px solid {C_BORDER};"><div style="font-size:8px;color:{C_DIM};text-transform:uppercase;">Stop (ATR)</div><div style="font-size:13px;font-weight:700;color:{C_RED};">{_dlr(p["stop"])}</div></td>
              <td style="padding:7px 12px;text-align:center;width:20%;border-left:1px solid {C_BORDER};"><div style="font-size:8px;color:{C_DIM};text-transform:uppercase;">R/R</div><div style="font-size:13px;font-weight:700;color:{C_WHITE};">1:{p["rr"]:.1f}</div></td>
              <td style="padding:7px 12px;text-align:center;width:20%;border-left:1px solid {C_BORDER};"><div style="font-size:8px;color:{C_DIM};text-transform:uppercase;">Size</div><div style="font-size:13px;font-weight:700;color:{C_WHITE};">{p["pos_size"]} shares</div></td>
            </tr></table>
          <div style="margin-top:6px;font-size:10px;color:{C_DIM};">
            Risk: {p["risk_pct"]:.1f}% | Reward: {p["reward_pct"]:.1f}%
            &ensp;|&ensp;{rsi_s} {macd_s} {ema_s}
            {f"&ensp;|&ensp;{earn_s}" if earn_s else ""}
          </div>
          <div style="font-size:10px;color:{C_DIM};margin-top:2px;">Fill: {p["fill_window"]}</div>
          {f'<div style="margin-top:4px;">{news_h}</div>' if news_h else ""}
        </div>'''
    return _sec(title, cards)


def html_tech_snapshot(holdings, picks_m, picks_s):
    """One-row-per-ticker technical snapshot table."""
    tickers_done = set()
    rows = ""
    all_items = [(h["ticker"], h["current_price"], h["tech"]) for h in holdings]
    for p in picks_m + picks_s:
        if p["ticker"] not in [x[0] for x in all_items]:
            all_items.append((p["ticker"], p["current_price"], p.get("tech", {})))
    for tk, price, t in all_items:
        if tk in tickers_done: continue
        tickers_done.add(tk)
        bg = C_CARD if len(tickers_done) % 2 == 0 else C_ALT
        rsi_c = C_RED if t.get("rsi_label") == "OVERBOUGHT" else C_GREEN if t.get("rsi_label") == "OVERSOLD" else C_TEXT
        macd_c = C_GREEN if "BULLISH" in t.get("macd_label","") else C_RED if "BEARISH" in t.get("macd_label","") else C_TEXT
        ema_c = C_GREEN if t.get("ema_label") == "GOLDEN CROSS" else C_RED
        vol_c = C_AMBER if t.get("vol_label") == "HIGH VOLUME" else C_DIM
        rows += f'''<tr style="background:{bg};">
          {_td(tk, color=C_WHITE, bold=True)}
          {_td(_dlr(price), color=C_WHITE)}
          <td style="padding:9px 12px;color:{rsi_c};font-size:11px;border-bottom:1px solid {C_BORDER};">{t.get("rsi","N/A")}</td>
          <td style="padding:9px 12px;color:{macd_c};font-size:11px;border-bottom:1px solid {C_BORDER};">{t.get("macd_label","N/A")}</td>
          {_td(t.get("bb_label","N/A"), size="11px")}
          <td style="padding:9px 12px;color:{ema_c};font-size:11px;border-bottom:1px solid {C_BORDER};">{t.get("ema_label","N/A")}</td>
          <td style="padding:9px 12px;color:{vol_c};font-size:11px;border-bottom:1px solid {C_BORDER};">{t.get("vol_label","N/A")}</td>
          {_td(_dlr(t.get("atr_stop") or 0), color=C_RED, size="11px")}
          {_td(_dlr(t.get("atr_target") or 0), color=C_GREEN, size="11px")}
        </tr>'''
    table = f'''<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
      <thead><tr style="background:{C_CARD};">{_th("Ticker")}{_th("Price")}{_th("RSI")}{_th("MACD")}{_th("BB")}{_th("EMA")}{_th("Volume")}{_th("ATR Stop")}{_th("ATR Target")}</tr></thead>
      <tbody>{rows}</tbody></table>'''
    return _sec("Technical Snapshot", table)


def html_movers(df, title):
    rows = ""
    for i, (_, r) in enumerate(df.iterrows()):
        bg = C_CARD if i % 2 == 0 else C_ALT
        rows += f'<tr style="background:{bg};">{_td(r["Ticker"], color=C_WHITE, bold=True)}{_td(_dlr(r["Previous Close"]), color=C_DIM)}<td style="padding:9px 12px;color:{_clr(r["Change %"])};font-weight:600;font-size:12px;border-bottom:1px solid {C_BORDER};">{_dlr(r["Current Price"])}</td><td style="padding:9px 12px;text-align:right;border-bottom:1px solid {C_BORDER};">{_pct_val(r["Change %"])}</td></tr>'
    table = f'<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;"><thead><tr style="background:{C_CARD};">{_th("Symbol")}{_th("Prev Close")}{_th("Price")}{_th("Change")}</tr></thead><tbody>{rows}</tbody></table>'
    return _sec(title, table)


def html_timeline():
    colors = [C_RED, C_AMBER, C_AMBER, C_BLUE, C_PURPLE]
    rows = ""
    for i, item in enumerate(STRATEGY_TIMELINE):
        bg = C_CARD if i % 2 == 0 else C_ALT; dc = colors[i % len(colors)]
        rows += f'<tr style="background:{bg};"><td style="padding:10px 12px;border-bottom:1px solid {C_BORDER};"><span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:{dc};margin-right:6px;vertical-align:middle;"></span><span style="font-size:11px;font-weight:700;color:{dc};">{item["period"]}</span></td><td style="padding:10px 12px;font-weight:600;color:{C_WHITE};font-size:12px;border-bottom:1px solid {C_BORDER};">{item["action"]}</td><td style="padding:10px 12px;color:{C_TEXT};font-size:11px;border-bottom:1px solid {C_BORDER};">{item["detail"]}</td></tr>'
    return _sec("Strategy Timeline", f'<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;"><thead><tr style="background:{C_CARD};">{_th("Period")}{_th("Action")}{_th("Detail")}</tr></thead><tbody>{rows}</tbody></table>')


def html_risk(rd):
    rc = C_GREEN if rd["risk_rating"]=="LOW" else C_RED if rd["risk_rating"]=="HIGH" else C_AMBER
    summary = f'''<div style="background:{C_ALT};border-radius:8px;padding:14px 16px;margin-bottom:12px;border:1px solid {C_BORDER};">
      <table width="100%" cellpadding="0" cellspacing="0"><tr>
        <td style="text-align:center;width:33%;"><div style="font-size:9px;color:{C_DIM};text-transform:uppercase;">Weighted Beta</div><div style="font-size:16px;font-weight:700;color:{C_WHITE};">{rd["weighted_beta"]:.2f}</div></td>
        <td style="text-align:center;width:34%;border-left:1px solid {C_BORDER};"><div style="font-size:9px;color:{C_DIM};text-transform:uppercase;">Risk Rating</div><div style="font-size:16px;font-weight:700;color:{rc};">{rd["risk_rating"]}</div></td>
        <td style="text-align:center;width:33%;border-left:1px solid {C_BORDER};"><div style="font-size:9px;color:{C_DIM};text-transform:uppercase;">1-Day 95% VaR</div><div style="font-size:16px;font-weight:700;color:{C_RED};">{_dlr(rd["var_95"])}</div></td>
      </tr></table></div>'''
    # Positions
    prows = ""
    for p in rd["positions"]:
        prows += f'<tr><td style="padding:7px 10px;color:{C_WHITE};font-weight:600;font-size:11px;border-bottom:1px solid {C_BORDER};">{p["ticker"]}</td><td style="padding:7px 10px;color:{C_TEXT};font-size:11px;border-bottom:1px solid {C_BORDER};">{p["weight"]:.1f}%</td><td style="padding:7px 10px;color:{C_TEXT};font-size:11px;border-bottom:1px solid {C_BORDER};">{p["beta"]:.2f}</td><td style="padding:7px 10px;color:{C_RED};font-size:11px;border-bottom:1px solid {C_BORDER};">{_dlr(p["risk_1d"])}</td></tr>'
    ptable = f'<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;"><thead><tr style="background:{C_CARD};">{_th("Ticker")}{_th("Weight")}{_th("Beta")}{_th("1-Day Risk")}</tr></thead><tbody>{prows}</tbody></table>'
    # Sectors
    srows = ""
    for sec, pct in sorted(rd["sectors"].items(), key=lambda x: -x[1]):
        srows += f'<tr><td style="padding:5px 10px;color:{C_TEXT};font-size:11px;border-bottom:1px solid {C_BORDER};">{sec}</td><td style="padding:5px 10px;color:{C_WHITE};font-weight:600;font-size:11px;border-bottom:1px solid {C_BORDER};">{pct:.1f}%</td></tr>'
    stable = f'<div style="margin-top:10px;"><div style="font-size:9px;color:{C_DIM};text-transform:uppercase;letter-spacing:0.8px;margin-bottom:4px;">Sector Exposure</div><table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;"><tbody>{srows}</tbody></table></div>' if srows else ""
    return _sec("Portfolio Risk Dashboard", summary + ptable + stable)


# =====================================================================
#  15. EMAIL ASSEMBLY & SEND
# =====================================================================
def build_html(sp, macro, catalysts, portfolio, picks_m, picks_s, gainers, losers, risk_d,
               premarket_movers=None):
    today_s = datetime.date.today().strftime("%A, %B %d, %Y")
    now_s = datetime.datetime.now().strftime("%I:%M %p")
    pre_html = html_premarket(premarket_movers or [])
    friday_html = html_friday_recap(portfolio)
    return f"""<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="margin:0;padding:0;background-color:{C_BG};font-family:'SF Pro Display','Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;-webkit-font-smoothing:antialiased;">
<div style="max-width:720px;margin:0 auto;padding:20px 10px;">
  {html_header(sp, today_s, now_s)}
  <div style="background:{C_CARD};border-radius:0 0 12px 12px;padding-bottom:8px;overflow:hidden;">
    {pre_html}
    {html_macro(macro)}
    {html_catalysts(catalysts)}
    {html_portfolio(portfolio)}
    {html_picks(picks_m, "Momentum Longs (1-3 Day Horizon)")}
    {html_picks(picks_s, "Swing Trades (2-4 Week Horizon)")}
    {html_tech_snapshot(portfolio, picks_m, picks_s)}
    {html_timeline()}
    {html_risk(risk_d)}
    {html_movers(gainers, "Top 10 Gainers")}
    {html_movers(losers, "Top 10 Losers")}
    {friday_html}
    <div style="margin:20px 20px 14px;padding:12px 16px;background:{C_ALT};border-radius:8px;border:1px solid {C_BORDER};text-align:center;">
      <div style="font-size:9px;color:{C_DIM};line-height:1.6;">
        Data: Yahoo Finance | Finnhub | Finviz | Google News<br>
        Generated by <span style="color:{C_AMBER};font-weight:600;">AI Stock Analyst v3</span>
        &ensp;|&ensp;{now_s} &ensp;|&ensp; For educational purposes only -- Not financial advice.
      </div>
    </div>
  </div>
</div></body></html>"""


def build_plain(sp, portfolio, picks_m, picks_s):
    lines = [f"AI Stock Analyst -- {datetime.date.today()}", "=" * 50,
             f"S&P 500: ${sp['price']:,.2f} ({sp['change']:+.2f}%)", ""]
    lines.append("PORTFOLIO:")
    for h in portfolio:
        lines.append(f"  {h['ticker']:6s} ${h['current_price']:>8.2f}  P&L {h['open_pnl_pct']:+.2f}%  -> {h['signal']}  {h['action']}")
    lines += ["", "MOMENTUM PICKS:"]
    for p in picks_m:
        lines.append(f"  {p['ticker']:6s} ${p['current_price']:>8.2f}  Entry ${p['entry']:.2f}  Target ${p['target']:.2f}  Stop ${p['stop']:.2f}  [{p['status']}]")
    lines += ["", "SWING PICKS:"]
    for p in picks_s:
        lines.append(f"  {p['ticker']:6s} ${p['current_price']:>8.2f}  Entry ${p['entry']:.2f}  Target ${p['target']:.2f}  Stop ${p['stop']:.2f}  [{p['status']}]")
    lines += ["", "Not financial advice."]
    return "\n".join(lines)


def send_email(html_body: str, text_body: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"AI Stock Report -- {datetime.date.today()}"
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECIPIENT_EMAIL
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))
    with smtplib.SMTP("smtp.gmail.com", 587) as srv:
        srv.starttls()
        srv.login(SENDER_EMAIL, EMAIL_PASSWORD)
        srv.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())
    print("  [OK] Email sent.")


# =====================================================================
#  16. SCHEDULER
# =====================================================================
TASK_NAME = "AI_Stock_Analyst_Daily"

def setup_scheduler():
    try:
        r = subprocess.run(["schtasks", "/Query", "/TN", TASK_NAME],
                           capture_output=True, text=True)
        if r.returncode == 0:
            print(f"  [OK] Task '{TASK_NAME}' exists."); return
    except FileNotFoundError:
        return
    py = sys.executable; script = os.path.abspath(__file__)
    cmd = ["schtasks", "/Create", "/TN", TASK_NAME,
           "/TR", f'"{py}" "{script}"', "/SC", "WEEKLY",
           "/D", "MON,TUE,WED,THU,FRI", "/ST", SCHEDULE_TIME, "/F"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 0:
            print(f"  [OK] Task created. Mon-Fri at {SCHEDULE_TIME}.")
        else:
            print(f"  [WARN] Task creation failed: {r.stderr.strip()}")
    except FileNotFoundError:
        pass


# =====================================================================
#  17. MAIN
# =====================================================================
def main():
    print("\n" + "=" * 55)
    print("   AI STOCK ANALYST v4 -- Starting")
    print("=" * 55 + "\n")

    setup_scheduler(); print()

    print("[1/7] Market summary...")
    sp = fetch_market_summary()
    print(f"  [OK] S&P 500: ${sp['price']:,.2f}  ({sp['change']:+.2f}%)  SPY: {sp['spy_mood']}")

    print("[2/7] Pre-market movers...")
    premarket = get_premarket_movers(MY_PORTFOLIO, WATCHLIST)
    print(f"  [OK] {len(premarket)} pre-market movers >2%")

    print("[3/7] Macro news & catalysts...")
    macro = get_macro_news()
    catalysts = get_weekly_catalysts()
    print(f"  [OK] {len(macro['headlines'])} headlines, {len(macro['risks'])} risk flags, {len(catalysts)} catalysts")

    print("[4/7] Portfolio analysis (composite scoring)...")
    portfolio = analyse_portfolio(MY_PORTFOLIO)
    risk_d = compute_risk_dashboard(portfolio)
    print(f"  [OK] Beta: {risk_d['weighted_beta']:.2f}  Risk: {risk_d['risk_rating']}  VaR: ${risk_d['var_95']:,.2f}")

    # ── Alert detection ───────────────────────────────────────────────────
    def _load_scores_cache() -> dict:
        try:
            return json.loads(SCORES_CACHE_FILE.read_text()) if SCORES_CACHE_FILE.exists() else {}
        except Exception:
            return {}

    def _save_scores_cache(results: list):
        cache = {r["ticker"]: r.get("score", 0) for r in results}
        SCORES_CACHE_FILE.write_text(json.dumps(cache, indent=2))

    def check_alerts(results: list) -> list:
        prev = _load_scores_cache()
        alerts = []
        for r in results:
            ticker = r["ticker"]
            rules = ALERT_RULES.get(ticker, ALERT_RULES["_default"])
            chg = abs(r.get("day_pnl_pct", 0))
            # Price move
            if chg >= rules["price_move_pct"]:
                direction = "UP" if r.get("day_pnl_pct", 0) > 0 else "DOWN"
                alerts.append({
                    "ticker": ticker, "type": "PRICE_MOVE", "severity": "HIGH",
                    "message": f"{ticker} is {direction} {chg:.1f}% today",
                    "time": datetime.datetime.now().strftime("%I:%M %p"),
                })
            # Signal score change
            curr_score = r.get("score", 0)
            prev_score = prev.get(ticker, curr_score)
            if abs(curr_score - prev_score) >= rules["min_score_change"]:
                alerts.append({
                    "ticker": ticker, "type": "SIGNAL_CHANGE", "severity": "HIGH",
                    "message": f"{ticker} signal score: {prev_score:+.1f} → {curr_score:+.1f} ({r.get('signal','?')})",
                    "time": datetime.datetime.now().strftime("%I:%M %p"),
                })
            # Earnings
            earn = r.get("earn", {})
            days = earn.get("days_to_earnings") if isinstance(earn, dict) else None
            if days is not None and 0 <= days <= rules["earnings_days"]:
                alerts.append({
                    "ticker": ticker, "type": "EARNINGS", "severity": "HIGH",
                    "message": f"{ticker} earnings in {days} day(s)",
                    "time": datetime.datetime.now().strftime("%I:%M %p"),
                })
        return alerts

    portfolio_alerts = check_alerts(portfolio)
    _save_scores_cache(portfolio)
    ALERTS_FILE.write_text(json.dumps(portfolio_alerts, indent=2))

    # Send short alert email if any HIGH alerts exist
    high_alerts = [a for a in portfolio_alerts if a["severity"] == "HIGH"]
    if high_alerts:
        alert_body = "\n".join(f"• {a['message']}" for a in high_alerts)
        alert_subject = f"Stock Alert — {', '.join(set(a['ticker'] for a in high_alerts))}"
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = alert_subject
            msg["From"] = SENDER_EMAIL
            msg["To"] = RECIPIENT_EMAIL
            msg.attach(MIMEText(alert_body, "plain"))
            with smtplib.SMTP("smtp.gmail.com", 587) as srv:
                srv.starttls()
                srv.login(SENDER_EMAIL, EMAIL_PASSWORD)
                srv.sendmail(SENDER_EMAIL, RECIPIENT_EMAIL, msg.as_string())
            print(f"  [OK] Alert email sent ({len(high_alerts)} alerts).")
        except Exception as e:
            print(f"  [WARN] Alert email failed: {e}")
        # Push to mobile app via api.py if running
        for alert in high_alerts:
            try:
                requests.post("http://localhost:8000/push-alert", json={
                    "ticker": alert["ticker"],
                    "message": alert["message"],
                }, timeout=3)
            except Exception:
                pass
    # ─────────────────────────────────────────────────────────────────────

    print("[5/7] Enriching smart picks...")
    picks_m = enrich_picks(MOMENTUM_PICKS)
    picks_s = enrich_picks(SWING_PICKS)

    print("[6/7] Scanning S&P 500...")
    tickers = fetch_sp500_tickers()
    df = analyse_stocks(tickers)
    if df.empty:
        print("  [ERROR] No data."); return
    gainers, losers = get_top_movers(df)

    print("[7/7] Building & sending report...")
    html = build_html(sp, macro, catalysts, portfolio, picks_m, picks_s, gainers, losers, risk_d,
                      premarket_movers=premarket)
    text = build_plain(sp, portfolio, picks_m, picks_s)
    send_email(html, text)

    print("\n" + "=" * 55)
    print("   DONE -- Check your inbox.")
    print("=" * 55 + "\n")


if __name__ == "__main__":
    main()
