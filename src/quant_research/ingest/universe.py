"""Ticker universe, FRED series map and private-company proxy definitions."""

from __future__ import annotations

CORE_TICKERS: list[str] = [
    "SPY",
    "QQQ",
    "IWM",
    "DIA",
    "VIX",
    # Sector ETFs
    "XLK",
    "XLF",
    "XLE",
    "XLV",
    "XLI",
    "XLY",
    "XLP",
    "XLB",
    "XLU",
    "XLRE",
]

PRIVATE_EXPOSURE_TICKERS: list[str] = [
    # Anthropic proxies
    "AMZN",
    "GOOG",
    "NVDA",
    "MSFT",
    "ARM",
    "SMCI",
    # SpaceX proxies
    "RKLB",
    "ASTS",
    "LUNR",
    "KTOS",
    "SPIR",
    # xAI / OpenAI proxies
    "TSLA",
    # Space / Defense
    "LMT",
    "NOC",
    "RTX",
]

# Reported funding-round valuations, written down by hand when public. A heuristic
# reference only, not a valuation model; update manually when new rounds close.
PRIVATE_VALUATIONS: dict[str, dict] = {
    "Anthropic": {
        "valuation_usd": 61_500_000_000,
        "round": "Series F",
        "date_reported": "2025-03-01",
        "source": "Bloomberg",
        "investors": ["AMZN", "GOOG"],
        "amazon_stake_pct": 0.27,
        "google_stake_pct": 0.10,
    },
    "SpaceX": {
        "valuation_usd": 350_000_000_000,
        "round": "Tender Offer",
        "date_reported": "2024-12-01",
        "source": "Bloomberg",
        "public_proxies": ["RKLB", "ASTS", "LUNR"],
    },
    "OpenAI": {
        "valuation_usd": 300_000_000_000,
        "round": "Series F+",
        "date_reported": "2025-01-15",
        "source": "WSJ",
        "investors": ["MSFT"],
        "msft_revenue_share": True,
    },
    "xAI": {
        "valuation_usd": 50_000_000_000,
        "round": "Series B",
        "date_reported": "2024-11-01",
        "source": "TechCrunch",
        "investors": ["TSLA"],
    },
    "Stripe": {
        "valuation_usd": 91_500_000_000,
        "round": "Secondary",
        "date_reported": "2024-10-01",
        "source": "Reuters",
        "public_proxies": ["SQ", "ADYEN"],
    },
}

# Proxy weights per private company (set by hand; see README "What it does not do").
PROXY_WEIGHTS: dict[str, dict[str, float]] = {
    "Anthropic": {
        "AMZN": 0.27,  # stake-weighted
        "GOOG": 0.10,
        "NVDA": 0.30,  # infrastructure dependency
        "MSFT": 0.15,  # sector comp
        "ARM": 0.18,  # chip architecture
    },
    "SpaceX": {
        "RKLB": 0.35,  # direct competitor / comp
        "ASTS": 0.25,  # satellite internet comp
        "LUNR": 0.20,  # NASA/lunar adjacency
        "KTOS": 0.20,  # defense/satellite
    },
    "OpenAI": {
        "MSFT": 0.60,  # revenue share
        "NVDA": 0.30,  # GPU dependency
        "ARM": 0.10,
    },
}

SPACE_ECONOMY_TICKERS: list[str] = ["RKLB", "ASTS", "LUNR", "KTOS"]

FRED_SERIES: dict[str, str] = {
    "DGS3MO": "treasury_3m",
    "DGS2": "treasury_2y",
    "DGS5": "treasury_5y",
    "DGS10": "treasury_10y",
    "DGS30": "treasury_30y",
    "T10Y2Y": "spread_10y_2y",  # Classic yield curve
    "T10Y3M": "spread_10y_3m",  # Recession indicator
    "BAMLH0A0HYM2": "hy_spread",  # High-yield credit spread
    "BAMLC0A0CM": "ig_spread",  # Investment-grade spread
    "DTWEXBGS": "dxy_broad",  # Dollar index (broad)
    "VIXCLS": "vix",
    "UNRATE": "unemployment",  # Monthly
    "CPIAUCSL": "cpi",  # Monthly
    "M2SL": "m2_money_supply",  # Monthly
    "FEDFUNDS": "fed_funds_rate",
    "MORTGAGE30US": "mortgage_30y",
}


def ingest_universe(extra: list[str] | None = None) -> list[str]:
    """Deduplicated, sorted list of every ticker the EOD pipeline fetches."""
    return sorted(set(CORE_TICKERS + PRIVATE_EXPOSURE_TICKERS + (extra or [])))
