"""Valuation and balance-sheet ratios with their labels."""

from __future__ import annotations

from collections.abc import Sequence


def peg_ratio(forward_pe: float | None, earnings_growth: float | None) -> float | None:
    """Forward P/E divided by earnings growth in percent.

    yfinance reports growth as a fraction (0.25 = 25%); values >= 1 are assumed to
    already be percentages. Returns ``None`` for missing or non-positive growth.
    """
    try:
        if forward_pe and earnings_growth and earnings_growth > 0:
            eg_pct = earnings_growth * 100 if earnings_growth < 1 else earnings_growth
            return round(forward_pe / eg_pct, 2) if eg_pct > 0 else None
    except (TypeError, ZeroDivisionError):
        pass
    return None


def peg_label(peg: float | None) -> str:
    if peg is None:
        return "N/A"
    if peg < 1:
        return "UNDERVALUED"
    if peg <= 2:
        return "FAIR"
    return "EXPENSIVE"


def altman_z(
    working_capital: float,
    retained_earnings: float,
    ebit: float,
    market_cap: float,
    total_liabilities: float,
    revenue: float,
    total_assets: float,
) -> float | None:
    """Original (public manufacturer) Altman Z-score. ``None`` if total assets <= 0."""
    if not total_assets or total_assets <= 0:
        return None
    x4_denom = total_liabilities if total_liabilities and total_liabilities > 0 else 1
    return round(
        1.2 * (working_capital / total_assets)
        + 1.4 * (retained_earnings / total_assets)
        + 3.3 * (ebit / total_assets)
        + 0.6 * (market_cap / x4_denom)
        + 1.0 * (revenue / total_assets),
        2,
    )


def altman_label(z: float | None) -> str:
    if z is None:
        return "N/A"
    if z > 2.99:
        return "SAFE"
    if z >= 1.81:
        return "GREY ZONE"
    return "DISTRESS"


def estimate_revision_label(estimates: Sequence[dict]) -> str:
    """Compare the two most recent consensus EPS estimates (newest first): >5% move = revision."""
    if len(estimates) < 2:
        return "N/A"
    current, prev = estimates[0].get("epsAvg"), estimates[1].get("epsAvg")
    if current is None or prev is None or prev == 0:
        return "N/A"
    rev_pct = (current - prev) / abs(prev) * 100
    if rev_pct > 5:
        return "ESTIMATES RISING"
    if rev_pct < -5:
        return "ESTIMATES FALLING"
    return "STABLE"


def earnings_surprise_pct(actual: float | None, estimate: float | None) -> float | None:
    if actual is None or not estimate:
        return None
    return round((actual - estimate) / abs(estimate) * 100, 1)


def format_market_cap(mcap: float | None) -> str:
    if mcap and mcap >= 1e12:
        return f"${mcap / 1e12:.2f}T"
    if mcap and mcap >= 1e9:
        return f"${mcap / 1e9:.2f}B"
    if mcap and mcap >= 1e6:
        return f"${mcap / 1e6:.1f}M"
    return "N/A"
