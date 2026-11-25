"""Market-wide views: S&P 500 movers, index summary, pre-market movers, crypto."""

from __future__ import annotations

import io
import logging

import pandas as pd
import requests

from quant_research.research.market_data import get_info
from quant_research.research.ticker_data import compute_technicals

log = logging.getLogger(__name__)

SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
USER_AGENT = "Mozilla/5.0 (compatible; quant-research-system/4.0)"


def parse_sp500_table(html: str) -> list[str]:
    """Ticker symbols from the Wikipedia constituents table, in Yahoo format (BRK.B -> BRK-B)."""
    table = pd.read_html(io.StringIO(html), flavor="html5lib")[0]
    return table["Symbol"].astype(str).str.replace(".", "-", regex=False).tolist()


def fetch_sp500_tickers() -> list[str]:
    resp = requests.get(SP500_URL, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()
    tickers = parse_sp500_table(resp.text)
    log.info("Fetched %d S&P 500 tickers.", len(tickers))
    return tickers


def analyse_stocks(tickers: list[str]) -> pd.DataFrame:
    """Previous close, current price and % change for each ticker, sorted best to worst."""
    recs = []
    total = len(tickers)
    for i, tk in enumerate(tickers, 1):
        try:
            info = get_info(tk)
            prev = info.get("previousClose") or info.get("regularMarketPreviousClose")
            cur = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("navPrice")
            if prev and cur and prev > 0:
                recs.append(
                    {
                        "Ticker": tk,
                        "Previous Close": round(prev, 2),
                        "Current Price": round(cur, 2),
                        "Change %": round((cur - prev) / prev * 100, 2),
                    }
                )
        except Exception:
            pass
        if i % 50 == 0 or i == total:
            log.info("Processed %d/%d", i, total)
    if not recs:
        return pd.DataFrame(columns=["Ticker", "Previous Close", "Current Price", "Change %"])
    df = pd.DataFrame(recs).sort_values("Change %", ascending=False).reset_index(drop=True)
    log.info("Analysed %d stocks.", len(df))
    return df


def get_top_movers(df: pd.DataFrame, n: int = 10) -> tuple[pd.DataFrame, pd.DataFrame]:
    return df.head(n).copy(), df.tail(n).sort_values("Change %", ascending=True).copy()


def spy_mood(rsi: float | None) -> str:
    if rsi and rsi > 60:
        return "Bullish"
    if rsi and rsi < 40:
        return "Bearish"
    return "Neutral"


def fetch_market_summary() -> dict:
    info = get_info("^GSPC")
    cur = info.get("regularMarketPrice") or info.get("previousClose") or 0
    prev = info.get("regularMarketPreviousClose") or info.get("previousClose") or 0
    chg = (cur - prev) / prev * 100 if prev else 0
    rsi = compute_technicals("SPY").get("rsi")
    return {"price": round(cur, 2), "change": round(chg, 2), "spy_rsi": rsi, "spy_mood": spy_mood(rsi)}


def get_premarket_movers(portfolio: list[dict], watchlist: list[str], threshold_pct: float = 2.0) -> list[dict]:
    """Holdings/watchlist names moving more than ``threshold_pct`` before the open."""
    movers = []
    try:
        tickers = set(watchlist) | {p["ticker"] for p in portfolio}
        for tk in sorted(tickers):
            info = get_info(tk)
            pre = info.get("preMarketPrice")
            prev = info.get("previousClose") or info.get("regularMarketPreviousClose")
            if pre and prev and prev > 0:
                chg = (pre - prev) / prev * 100
                if abs(chg) > threshold_pct:
                    movers.append(
                        {
                            "ticker": tk,
                            "pre_price": round(pre, 2),
                            "prev_close": round(prev, 2),
                            "change_pct": round(chg, 2),
                        }
                    )
    except Exception:
        pass
    return sorted(movers, key=lambda x: abs(x["change_pct"]), reverse=True)


def get_crypto_prices(coins: list[str] | None = None) -> dict:
    """CoinGecko public API (no key): price, 24h change, market cap, volume."""
    coins = coins or ["bitcoin", "ethereum", "solana", "binancecoin", "ripple"]
    params = {
        "ids": ",".join(coins),
        "vs_currencies": "usd",
        "include_24hr_change": "true",
        "include_market_cap": "true",
        "include_24hr_vol": "true",
    }
    try:
        return requests.get("https://api.coingecko.com/api/v3/simple/price", params=params, timeout=6).json()
    except Exception:
        return {}


def get_fear_greed() -> dict:
    """Crypto Fear & Greed Index (alternative.me, no key)."""
    try:
        d = requests.get("https://api.alternative.me/fng/", timeout=5).json()["data"][0]
        return {"value": int(d["value"]), "label": d["value_classification"]}
    except Exception:
        return {"value": 50, "label": "Neutral"}
