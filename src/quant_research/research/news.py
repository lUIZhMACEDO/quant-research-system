"""Headlines (yfinance, Finnhub, Google News RSS), LLM sentiment, and macro risk flags."""

from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Iterable, Mapping
from datetime import timedelta
from difflib import SequenceMatcher
from urllib.parse import quote_plus

import feedparser
import requests
import yfinance as yf

from quant_research.config import get_settings
from quant_research.research.market_data import fh_call

log = logging.getLogger(__name__)

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


def is_similar(a: str, b: str, thresh: float = 0.80) -> bool:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio() > thresh


class HeadlineSet:
    """Accumulates headlines, dropping near-duplicates (same story from several feeds)."""

    def __init__(self) -> None:
        self.items: list[dict] = []

    def add(self, title: str, link: str = "", publisher: str = "") -> None:
        if not title or any(is_similar(title, i["title"]) for i in self.items):
            return
        self.items.append({"title": title, "link": link, "publisher": publisher})


def flag_macro_risks(
    titles: Iterable[str], portfolio_tickers: list[str], keywords: Mapping[str, Mapping]
) -> list[dict]:
    """Keyword scan of headlines -> per-ticker risk flags. HIGH beats MEDIUM for a ticker."""
    text = " ".join(titles).lower()
    flagged: dict[str, dict] = {}
    for kw, info in keywords.items():
        if kw not in text:
            continue
        tickers = portfolio_tickers if "*" in info["tickers"] else info["tickers"]
        for tk in tickers:
            if tk not in flagged or info["level"] == "HIGH":
                flagged[tk] = {"level": info["level"], "reason": info["reason"], "keyword": kw}
    return [{"ticker": tk, **data} for tk, data in flagged.items()]


def google_news(query: str, n: int = 3) -> list[dict]:
    try:
        feed = feedparser.parse(f"https://news.google.com/rss/search?q={quote_plus(query)}+stock&hl=en-US")
        return [
            {
                "title": e.get("title", ""),
                "link": e.get("link", ""),
                "publisher": e.get("source", {}).get("title", "Google News"),
            }
            for e in feed.entries[:n]
        ]
    except Exception:
        return []


def score_news_sentiment(ticker: str, headlines: list[str]) -> float:
    """LLM sentiment score in [-1, +1] for the headlines. 0.0 if the API is unavailable."""
    settings = get_settings()
    if not settings.anthropic_api_key or not headlines:
        return 0.0
    bullet_list = "\n".join(f"- {h}" for h in headlines if h)
    prompt = (
        f"You are a financial analyst. Rate the overall sentiment of these news "
        f"headlines for {ticker} as a single float between -1.0 (very bearish) and "
        f"+1.0 (very bullish). Return ONLY the number, no explanation.\n"
        f"Headlines:\n{bullet_list}"
    )
    try:
        resp = requests.post(
            ANTHROPIC_URL,
            headers={
                "x-api-key": settings.anthropic_api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": settings.anthropic_model,
                "max_tokens": 10,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=15,
        )
        if resp.status_code == 200:
            val = float(resp.json()["content"][0]["text"].strip())
            return max(-1.0, min(1.0, val))
    except Exception:
        pass
    return 0.0


def strategy_note(ticker: str, signal: str, rsi: float, analyst_buy: int, analyst_sell: int, fallback: str) -> str:
    """One-sentence strategy note from the LLM, or ``fallback`` when the API is unavailable."""
    settings = get_settings()
    if not settings.anthropic_api_key:
        return fallback
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        prompt = (
            f"Stock: {ticker}. Signal: {signal}. RSI: {rsi:.0f}. "
            f"Analyst ratings: {analyst_buy} buy, {analyst_sell} sell. "
            f"Write one concise sentence (max 20 words) of actionable strategy advice for this position. "
            f"No disclaimers. Plain text only."
        )
        msg = client.messages.create(
            model=settings.anthropic_model, max_tokens=60, messages=[{"role": "user", "content": prompt}]
        )
        return msg.content[0].text.strip()
    except Exception:
        return fallback


def get_ticker_news(ticker: str) -> dict:
    """Up to three deduplicated headlines plus a sentiment score."""
    hs = HeadlineSet()
    try:
        for a in (yf.Ticker(ticker).news or [])[:3]:
            hs.add(a.get("title", ""), a.get("link", ""), a.get("publisher", ""))
    except Exception:
        pass

    today = dt.date.today()
    ago = today - timedelta(days=3)
    fh_news = fh_call("company_news", ticker, _from=ago.strftime("%Y-%m-%d"), to=today.strftime("%Y-%m-%d"))
    if fh_news and isinstance(fh_news, list):
        for a in fh_news[:3]:
            hs.add(a.get("headline", ""), a.get("url", ""), a.get("source", "Finnhub"))

    for a in google_news(ticker, 3):
        hs.add(a["title"], a["link"], a["publisher"])

    items = hs.items[:3]
    sentiment = score_news_sentiment(ticker, [i["title"] for i in items])
    return {"headlines": items, "sentiment_score": round(sentiment, 2)}


def get_macro_news(portfolio_tickers: list[str], keywords: Mapping[str, Mapping]) -> dict:
    """General market headlines and keyword-based portfolio risk flags."""
    hs = HeadlineSet()
    gen = fh_call("general_news", "general", min_id=0)
    if gen and isinstance(gen, list):
        for a in gen[:5]:
            hs.add(a.get("headline", ""), a.get("url", ""), a.get("source", ""))
    for a in google_news("stock market today", 5):
        hs.add(a["title"], a["link"], a["publisher"])

    risks = flag_macro_risks((h["title"] for h in hs.items), portfolio_tickers, keywords)
    return {"headlines": hs.items[:8], "risks": risks}
