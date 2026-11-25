"""Private-company exposure scores built from public proxy tickers (a heuristic, not a valuation)."""

from __future__ import annotations

from collections.abc import Mapping

from quant_research.ingest.universe import PROXY_WEIGHTS, SPACE_ECONOMY_TICKERS


def compute_proxy_scores(
    prices_today: Mapping[str, Mapping], weights: Mapping[str, Mapping[str, float]] = PROXY_WEIGHTS
) -> dict[str, float]:
    """Weighted average 5-day momentum of each private company's proxies.

    ``prices_today`` maps ticker -> {"momentum_5d": float, ...}. Proxies with no
    data are dropped and the remaining weights renormalised. Companies with no
    usable proxy are omitted.
    """
    scores: dict[str, float] = {}
    for company, company_weights in weights.items():
        total_w = 0.0
        score = 0.0
        for ticker, w in company_weights.items():
            m5d = prices_today.get(ticker, {}).get("momentum_5d")
            if m5d is not None:
                score += m5d * w
                total_w += w
        if total_w > 0:
            scores[company] = round(score / total_w, 6)
    return scores


def build_space_economy_index(
    prices_today: Mapping[str, Mapping], tickers: list[str] = SPACE_ECONOMY_TICKERS
) -> float | None:
    """Equal-weight 5-day momentum of the space basket. Positive = sector in favour."""
    vals = [prices_today.get(t, {}).get("momentum_5d") for t in tickers]
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    return round(sum(vals) / len(vals), 6)
