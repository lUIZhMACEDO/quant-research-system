"""Portfolio risk: weighted beta, sector exposure and 1-day historical VaR."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np


def risk_rating(weighted_beta: float) -> str:
    if weighted_beta < 0.8:
        return "LOW"
    if weighted_beta < 1.2:
        return "MEDIUM"
    return "HIGH"


def historical_var(
    weighted_returns: Sequence[tuple[float, np.ndarray]], total_value: float, confidence: float = 0.95
) -> float:
    """1-day historical VaR of the weighted portfolio, in dollars (a positive number).

    ``weighted_returns`` is ``[(weight, daily_returns), ...]``. Series are aligned
    on their most recent common length.
    """
    if not weighted_returns:
        return 0.0
    min_len = min(len(r) for _, r in weighted_returns)
    if min_len == 0:
        return 0.0
    port = np.zeros(min_len)
    for w, r in weighted_returns:
        port += w * np.asarray(r[-min_len:], dtype=float)
    return float(abs(np.percentile(port, (1 - confidence) * 100)) * total_value)


def portfolio_risk(holdings: Sequence[Mapping], returns_by_ticker: Mapping[str, np.ndarray]) -> dict:
    """Risk summary for analysed holdings.

    Each holding needs ``ticker``, ``market_value`` and ``fins`` (with ``beta`` and
    ``sector``). Missing betas count as 1.0.
    """
    total_val = sum(h["market_value"] for h in holdings)
    if total_val == 0:
        return {"weighted_beta": 0, "risk_rating": "N/A", "var_95": 0, "sectors": {}, "positions": []}

    w_beta = 0.0
    sectors: dict[str, float] = {}
    weighted_returns: list[tuple[float, np.ndarray]] = []
    positions = []
    for h in holdings:
        w = h["market_value"] / total_val
        beta = h["fins"].get("beta") or 1.0
        w_beta += w * beta
        sec = h["fins"].get("sector", "Unknown")
        sectors[sec] = sectors.get(sec, 0) + w * 100
        rets = returns_by_ticker.get(h["ticker"])
        if rets is not None and len(rets) > 0:
            weighted_returns.append((w, np.asarray(rets, dtype=float)))
        positions.append(
            {
                "ticker": h["ticker"],
                "weight": round(w * 100, 1),
                "beta": round(beta, 2),
                "risk_1d": round(beta * 0.02 * h["market_value"], 2),
            }
        )

    return {
        "weighted_beta": round(w_beta, 2),
        "risk_rating": risk_rating(w_beta),
        "var_95": round(historical_var(weighted_returns, total_val), 2),
        "sectors": sectors,
        "positions": positions,
    }
