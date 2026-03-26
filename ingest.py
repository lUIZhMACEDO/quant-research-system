"""
ingest.py — EOD Data Pipeline
==============================
Runs after market close (4:05 PM ET) to fetch, compute, and store all data
needed by the signal engine and dashboard.

Pipeline order:
  1. Fetch OHLCV for all tickers (yfinance primary, Tiingo fallback)
    2. Fetch FRED macro snapshot (yields, spreads, DXY, VIX)
      3. Recompute technicals for today's bar only
        4. Pull fundamentals snapshot (P/E, EV/EBITDA, FCF yield, etc.)
          5. Compute private company proxy scores
            6. Run signal generation and append to signal_log
              7. Re-run walk-forward ML predictions
                8. Data quality checks — flag missing tickers, stale bars
                  9. Write all results to SQLite (WAL mode)
                  """

from __future__ import annotations

import os
import sqlite3
import datetime
import logging
import time
from typing import Optional

import pandas as pd
import numpy as np
import requests
import yfinance as yf
from ta.momentum import RSIIndicator, StochRSIIndicator
from ta.trend import MACD, EMAIndicator, SMAIndicator
from ta.volatility import BollingerBands, AverageTrueRange

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DB_PATH       = os.getenv("DB_PATH", "quant.db")
TIINGO_KEY    = os.getenv("TIINGO_API_KEY", "")          # Optional upgrade
FRED_BASE     = "https://fred.stlouisfed.org/graph/fredgraph.csv"
LOOKBACK_DAYS = 365 * 5                                  # 5-year history

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Universe
# ---------------------------------------------------------------------------

CORE_TICKERS = [
      "SPY", "QQQ", "IWM", "DIA", "VIX",
      # Sector ETFs
      "XLK", "XLF", "XLE", "XLV", "XLI", "XLY", "XLP", "XLB", "XLU", "XLRE",
]

PRIVATE_EXPOSURE_TICKERS = [
      # Anthropic proxies
    "AMZN", "GOOG", "NVDA", "MSFT", "ARM", "SMCI",
      # SpaceX proxies
      "RKLB", "ASTS", "LUNR", "KTOS", "SPIR",
      # xAI / OpenAI proxies
      "TSLA",
      # Space / Defense
      "LMT", "NOC", "RTX",
]

# Known funding round valuations — update manually when new rounds close
PRIVATE_VALUATIONS: dict[str, dict] = {
      "Anthropic": {
                "valuation_usd":    61_500_000_000,
                "round":            "Series F",
                "date_reported":    "2025-03-01",
                "source":           "Bloomberg",
                "investors":        ["AMZN", "GOOG"],
                "amazon_stake_pct": 0.27,
                "google_stake_pct": 0.10,
      },
      "SpaceX": {
                "valuation_usd":   350_000_000_000,
                "round":           "Tender Offer",
                "date_reported":   "2024-12-01",
                "source":          "Bloomberg",
                "public_proxies":  ["RKLB", "ASTS", "LUNR"],
      },
      "OpenAI": {
                "valuation_usd":   300_000_000_000,
                "round":           "Series F+",
                "date_reported":   "2025-01-15",
                "source":          "WSJ",
                "investors":       ["MSFT"],
                "msft_revenue_share": True,
      },
      "xAI": {
                "valuation_usd":  50_000_000_000,
                "round":          "Series B",
                "date_reported":  "2024-11-01",
                "source":         "TechCrunch",
                "investors":      ["TSLA"],
      },
      "Stripe": {
                "valuation_usd":  91_500_000_000,
                "round":          "Secondary",
                "date_reported":  "2024-10-01",
                "source":         "Reuters",
                "public_proxies": ["SQ", "ADYEN"],
      },
}

# Proxy score weights per private company
PROXY_WEIGHTS: dict[str, dict[str, float]] = {
      "Anthropic": {
                "AMZN": 0.27,   # stake-weighted
                "GOOG": 0.10,
                "NVDA": 0.30,   # infrastructure dependency
                "MSFT": 0.15,   # sector comp
                "ARM":  0.18,   # chip architecture
      },
      "SpaceX": {
                "RKLB": 0.35,   # direct competitor / comp
                "ASTS": 0.25,   # satellite internet comp
                "LUNR": 0.20,   # NASA/lunar adjacency
                "KTOS": 0.20,   # defense/satellite
      },
      "OpenAI": {
                "MSFT": 0.60,   # 49% revenue share
                "NVDA": 0.30,   # GPU dependency
                "ARM":  0.10,
      },
}

# ---------------------------------------------------------------------------
# FRED macro series
# ---------------------------------------------------------------------------

FRED_SERIES: dict[str, str] = {
      "DGS3MO":     "treasury_3m",
      "DGS2":       "treasury_2y",
      "DGS5":       "treasury_5y",
      "DGS10":      "treasury_10y",
      "DGS30":      "treasury_30y",
      "T10Y2Y":     "spread_10y_2y",       # Classic yield curve
      "T10Y3M":     "spread_10y_3m",       # Recession indicator
      "BAMLH0A0HYM2": "hy_spread",         # High-yield credit spread
      "BAMLC0A0CM": "ig_spread",           # Investment-grade spread
      "DTWEXBGS":   "dxy_broad",           # Dollar index (broad)
      "VIXCLS":     "vix",
      "UNRATE":     "unemployment",        # Monthly
      "CPIAUCSL":   "cpi",                 # Monthly
      "M2SL":       "m2_money_supply",     # Monthly
      "FEDFUNDS":   "fed_funds_rate",
      "MORTGAGE30US": "mortgage_30y",
}


def fetch_fred_series(series_id: str, lookback_days: int = 30) -> Optional[float]:
      """Fetch the latest value for a FRED series. Returns None on failure."""
      try:
                since = (datetime.date.today() - datetime.timedelta(days=lookback_days)).isoformat()
                url = f"{FRED_BASE}?id={series_id}&vintage_date={since}"
                df = pd.read_csv(url, parse_dates=["DATE"], index_col="DATE")
                df.replace(".", pd.NA, inplace=True)
                df = df.dropna()
                if df.empty:
                              return None
                          return float(df.iloc[-1, 0])
except Exception as e:
        log.warning(f"FRED fetch failed for {series_id}: {e}")
        return None


def fetch_all_macro() -> dict[str, Optional[float]]:
      """Fetch all FRED macro series. Returns dict of label -> latest value."""
      result: dict[str, Optional[float]] = {}
      for series_id, label in FRED_SERIES.items():
                result[label] = fetch_fred_series(series_id)
                time.sleep(0.3)   # Be polite to FRED API
    # Derived: yield curve slope (10y - 2y already in T10Y2Y, but compute full slope)
      t10 = result.get("treasury_10y")
    t3m = result.get("treasury_3m")
    t2  = result.get("treasury_2y")
    if t10 and t3m:
              result["curve_slope_10y_3m"] = round(t10 - t3m, 4)
          if t10 and t2:
                    result["curve_slope_10y_2y"] = round(t10 - t2, 4)
                # HY - IG spread differential
                hy = result.get("hy_spread")
    ig = result.get("ig_spread")
    if hy and ig:
              result["hy_ig_differential"] = round(hy - ig, 4)
          return result


# ---------------------------------------------------------------------------
# OHLCV fetch (yfinance primary)
# ---------------------------------------------------------------------------

def fetch_ohlcv(ticker: str, period: str = "5y") -> Optional[pd.DataFrame]:
      """Fetch adjusted OHLCV from yfinance. Returns None on failure."""
      try:
                df = yf.download(ticker, period=period, auto_adjust=True, progress=False)
                if df.empty or len(df) < 20:
                              return None
                          df.columns = [c.lower() for c in df.columns]
                df.index.name = "date"
                df["ticker"] = ticker
                return df[["ticker", "open", "high", "low", "close", "volume"]]
except Exception as e:
        log.warning(f"yfinance fetch failed for {ticker}: {e}")
        return None


# ---------------------------------------------------------------------------
# Technicals — vectorized, full-series
# ---------------------------------------------------------------------------

def compute_technicals(df: pd.DataFrame) -> pd.DataFrame:
      """
          Compute all technical indicators in a single vectorized pass.
              Avoids the O(n^2) row-by-row bug in the original implementation.
                  """
      close = df["close"]
      high  = df["high"]
      low   = df["low"]
      vol   = df["volume"]

    # RSI
      df["rsi_14"]  = RSIIndicator(close, window=14).rsi()
      df["rsi_zscore_252"] = (df["rsi_14"] - df["rsi_14"].rolling(252).mean()) / df["rsi_14"].rolling(252).std()

    # MACD
      macd = MACD(close)
      df["macd"]        = macd.macd()
      df["macd_signal"] = macd.macd_signal()
      df["macd_hist"]   = macd.macd_diff()

    # Bollinger Bands
      bb = BollingerBands(close, window=20, window_dev=2)
    df["bb_upper"]    = bb.bollinger_hband()
    df["bb_lower"]    = bb.bollinger_lband()
    df["bb_mid"]      = bb.bollinger_mavg()
    df["bb_pct"]      = bb.bollinger_pband()   # 0=lower band, 1=upper band

    # Moving Averages
    df["sma_50"]  = SMAIndicator(close, window=50).sma_indicator()
    df["sma_200"] = SMAIndicator(close, window=200).sma_indicator()
    df["ema_20"]  = EMAIndicator(close, window=20).ema_indicator()

    # Golden / Death Cross
    df["golden_cross"] = (df["sma_50"] > df["sma_200"]).astype(int)
    df["cross_signal"] = df["golden_cross"].diff().fillna(0)   # +1=golden, -1=death

    # ATR — realized volatility proxy
    atr = AverageTrueRange(high, low, close, window=14)
    df["atr_14"]        = atr.average_true_range()
    df["atr_pct"]       = df["atr_14"] / close   # normalized ATR

    # Realized volatility (21-day annualized)
    df["realized_vol_21d"] = close.pct_change().rolling(21).std() * (252 ** 0.5)

    # Momentum
    df["momentum_5d"]   = close.pct_change(5)
    df["momentum_21d"]  = close.pct_change(21)
    df["momentum_63d"]  = close.pct_change(63)
    df["momentum_252d"] = close.pct_change(252)

    # Volume z-score
    df["vol_zscore_20d"] = (vol - vol.rolling(20).mean()) / vol.rolling(20).std()

    # Hurst Exponent (simplified — uses R/S analysis on 64-bar windows)
    df["hurst_64"]  = _rolling_hurst(close, window=64)

    # Cross-sectional rank columns — filled during portfolio-level computation
    df["rsi_rank"]  = np.nan
    df["mom_rank"]  = np.nan

    return df


def _rolling_hurst(series: pd.Series, window: int = 64) -> pd.Series:
      """
          Estimate the Hurst Exponent using simplified R/S analysis.
              H > 0.5 = trending, H < 0.5 = mean-reverting, H ~0.5 = random walk.
                  """
      result = [np.nan] * len(series)
      arr = series.values
      for i in range(window, len(arr)):
                chunk = arr[i - window: i]
                try:
                              lags  = range(2, min(20, window // 4))
                              rs_vals = []
                              for lag in lags:
                                                sub   = chunk[:lag]
                                                mean  = np.mean(sub)
                                                dev   = np.cumsum(sub - mean)
                                                r     = np.max(dev) - np.min(dev)
                                                s     = np.std(sub, ddof=1)
                                                if s > 0:
                                                                      rs_vals.append((lag, r / s))
                                                              if len(rs_vals) >= 4:
                                                                                lags_arr = np.log([x[0] for x in rs_vals])
                                                                                rs_arr   = np.log([x[1] for x in rs_vals])
                                                                                h        = np.polyfit(lags_arr, rs_arr, 1)[0]
                                                                                result[i] = round(float(h), 4)
                except Exception:
                              pass
                      return pd.Series(result, index=series.index)


# ---------------------------------------------------------------------------
# Fundamentals — yfinance .info fallback
# ---------------------------------------------------------------------------

def fetch_fundamentals(ticker: str) -> dict:
      """
          Fetch key fundamental ratios. Uses yfinance .info as free source.
              Upgrade path: swap for Tiingo or IEX Cloud for cleaner data.
                  """
      try:
                info = yf.Ticker(ticker).info
                return {
                    "ticker":             ticker,
                    "date":               datetime.date.today().isoformat(),
                    "pe_ttm":             info.get("trailingPE"),
                    "pe_forward":         info.get("forwardPE"),
                    "pb":                 info.get("priceToBook"),
                    "ps_ttm":             info.get("priceToSalesTrailing12Months"),
                    "ev_ebitda":          info.get("enterpriseToEbitda"),
                    "ev_revenue":         info.get("enterpriseToRevenue"),
                    "fcf_yield":          _safe_fcf_yield(info),
                    "earnings_growth_yoy": info.get("earningsGrowth"),
                    "revenue_growth_yoy": info.get("revenueGrowth"),
                    "debt_to_equity":     info.get("debtToEquity"),
                    "current_ratio":      info.get("currentRatio"),
                    "roe":                info.get("returnOnEquity"),
                    "profit_margin":      info.get("profitMargins"),
                    "analyst_target_price": info.get("targetMeanPrice"),
                    "analyst_rating":     info.get("recommendationMean"),   # 1=Strong Buy, 5=Sell
                    "num_analysts":       info.get("numberOfAnalystOpinions"),
                    "short_pct_float":    info.get("shortPercentOfFloat"),
                    "insider_pct":        info.get("heldPercentInsiders"),
                }
except Exception as e:
        log.warning(f"Fundamentals fetch failed for {ticker}: {e}")
        return {"ticker": ticker, "date": datetime.date.today().isoformat()}


def _safe_fcf_yield(info: dict) -> Optional[float]:
      """FCF yield = Free Cash Flow / Market Cap."""
      try:
                fcf   = info.get("freeCashflow")
                mcap  = info.get("marketCap")
                if fcf and mcap and mcap > 0:
                              return round(fcf / mcap, 6)
      except Exception:
                pass
            return None


# ---------------------------------------------------------------------------
# Private company proxy scores
# ---------------------------------------------------------------------------

def compute_proxy_scores(prices_today: dict[str, dict]) -> dict[str, float]:
      """
          Compute a synthetic exposure score for each tracked private company
              based on the 5-day momentum of their public proxy stocks, weighted
                  by stake size / relevance.

                      prices_today: { "AMZN": {"momentum_5d": 0.023, ...}, ... }
                          Returns: { "Anthropic": 0.0142, "SpaceX": -0.0031, ... }
                              """
    scores: dict[str, float] = {}
    for company, weights in PROXY_WEIGHTS.items():
              total_w = 0.0
              score   = 0.0
              for ticker, w in weights.items():
                            m5d = prices_today.get(ticker, {}).get("momentum_5d")
                            if m5d is not None:
                                              score   += m5d * w
                                              total_w += w
                                      if total_w > 0:
                                                    scores[company] = round(score / total_w, 6)
                                            return scores


def build_space_economy_index(prices_today: dict[str, dict]) -> Optional[float]:
      """
          Equal-weight index of RKLB + ASTS + LUNR + KTOS.
              Positive = space sector in favor, negative = out of favor.
                  """
    space_tickers = ["RKLB", "ASTS", "LUNR", "KTOS"]
    vals = [prices_today.get(t, {}).get("momentum_5d") for t in space_tickers]
    vals = [v for v in vals if v is not None]
    if not vals:
              return None
          return round(sum(vals) / len(vals), 6)


# ---------------------------------------------------------------------------
# SQLite persistence (WAL mode)
# ---------------------------------------------------------------------------

def get_db() -> sqlite3.Connection:
      con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con


def init_schema(con: sqlite3.Connection) -> None:
      """Create all tables if they don't exist. See schema.sql for full docs."""
    con.executescript(open("schema.sql").read())
    con.commit()


def upsert_prices(con: sqlite3.Connection, df: pd.DataFrame) -> None:
      df_clean = df.copy()
    df_clean["date"] = df_clean.index.astype(str)
    df_clean.to_sql("prices", con, if_exists="append", index=False,
                                        method="ignore")  # ignore = don't duplicate existing rows


def upsert_indicators(con: sqlite3.Connection, df: pd.DataFrame) -> None:
      df_clean = df.copy()
    df_clean["date"] = df_clean.index.astype(str)
    cols = ["ticker", "date", "rsi_14", "rsi_zscore_252", "macd", "macd_signal",
                        "macd_hist", "bb_pct", "sma_50", "sma_200", "ema_20", "golden_cross",
                        "atr_14", "atr_pct", "realized_vol_21d", "momentum_5d", "momentum_21d",
                        "momentum_63d", "momentum_252d", "vol_zscore_20d", "hurst_64"]
    df_clean[[c for c in cols if c in df_clean.columns]].to_sql(
              "indicators", con, if_exists="append", index=False, method="ignore")


def upsert_macro(con: sqlite3.Connection, macro: dict, date: str) -> None:
      row = {"date": date, **macro}
    pd.DataFrame([row]).to_sql("macro_daily", con, if_exists="append",
                                                              index=False, method="ignore")


def upsert_fundamentals(con: sqlite3.Connection, fund: dict) -> None:
      pd.DataFrame([fund]).to_sql("fundamentals", con, if_exists="append",
                                                                  index=False, method="ignore")


def log_proxy_scores(con: sqlite3.Connection, scores: dict, date: str) -> None:
      rows = [{"date": date, "private_company": k, "proxy_score": v}
                          for k, v in scores.items()]
    pd.DataFrame(rows).to_sql("proxy_scores", con, if_exists="append",
                                                             index=False, method="ignore")


def log_data_quality(con: sqlite3.Connection, ticker: str,
                                          issue: str, date: str) -> None:
                                                pd.DataFrame([{"date": date, "ticker": ticker, "issue": issue}]).to_sql(
                                                          "data_quality", con, if_exists="append", index=False)


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------

def run_pipeline(tickers: Optional[list[str]] = None) -> None:
      """Run the full EOD ingest pipeline."""
    today = datetime.date.today().isoformat()
    all_tickers = list(set(CORE_TICKERS + PRIVATE_EXPOSURE_TICKERS + (tickers or [])))

    con = get_db()
    init_schema(con)

    # ---- 1. OHLCV --------------------------------------------------------
    prices_today: dict[str, dict] = {}
    log.info(f"Fetching OHLCV for {len(all_tickers)} tickers...")
    for ticker in all_tickers:
              df = fetch_ohlcv(ticker, period="5y")
              if df is None or df.empty:
                            log.warning(f"No data for {ticker}")
                            log_data_quality(con, ticker, "no_ohlcv", today)
                            continue
                        # Check for stale data
                        last_date = df.index[-1].date()
        if (datetime.date.today() - last_date).days > 3:
                      log_data_quality(con, ticker, f"stale_{last_date}", today)
                  upsert_prices(con, df)

        # ---- 2. Technicals (vectorized full series) ---------------------
        df_ind = compute_technicals(df.copy())
        upsert_indicators(con, df_ind)

        # Save today's momentum for proxy scores
        if len(df_ind) > 0:
                      last = df_ind.iloc[-1]
                      prices_today[ticker] = {
                          "momentum_5d":  last.get("momentum_5d"),
                          "momentum_21d": last.get("momentum_21d"),
                          "rsi_14":       last.get("rsi_14"),
                          "realized_vol": last.get("realized_vol_21d"),
                      }
                  con.commit()
        time.sleep(0.2)

    # ---- 3. FRED Macro ---------------------------------------------------
    log.info("Fetching FRED macro data...")
    macro = fetch_all_macro()
    upsert_macro(con, macro, today)
    con.commit()

    # ---- 4. Fundamentals -------------------------------------------------
    log.info("Fetching fundamentals...")
    for ticker in all_tickers:
              fund = fetch_fundamentals(ticker)
        upsert_fundamentals(con, fund)
        time.sleep(0.5)
    con.commit()

    # ---- 5. Private company proxy scores --------------------------------
    log.info("Computing private company proxy scores...")
    proxy_scores = compute_proxy_scores(prices_today)
    proxy_scores["space_economy_index"] = build_space_economy_index(prices_today)
    log_proxy_scores(con, proxy_scores, today)
    con.commit()

    # ---- 6. Data quality summary ----------------------------------------
    cur = con.execute("SELECT COUNT(*) FROM data_quality WHERE date=?", (today,))
    issues = cur.fetchone()[0]
    if issues:
              log.warning(f"Data quality: {issues} issues logged for {today}")
else:
        log.info("Data quality: clean run, no issues.")

    con.close()
    log.info(f"Pipeline complete for {today}.")


if __name__ == "__main__":
      run_pipeline()
