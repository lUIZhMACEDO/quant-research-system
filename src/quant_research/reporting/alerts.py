"""Holding alerts: big price moves, score jumps since the last run, and imminent earnings."""

from __future__ import annotations

import datetime as dt
import json
import logging
from collections.abc import Mapping, Sequence
from pathlib import Path

log = logging.getLogger(__name__)


def check_alerts(
    results: Sequence[Mapping],
    prev_scores: Mapping[str, float],
    rules: Mapping[str, Mapping[str, float]],
    now: dt.datetime | None = None,
) -> list[dict]:
    """Return alert dicts for analysed holdings.

    ``rules`` is keyed by ticker with a ``"_default"`` fallback; each rule has
    ``price_move_pct``, ``min_score_change`` and ``earnings_days``.
    """
    stamp = (now or dt.datetime.now()).strftime("%I:%M %p")
    alerts: list[dict] = []
    for r in results:
        ticker = r["ticker"]
        rule = rules.get(ticker, rules["_default"])
        day_pct = r.get("day_pnl_pct", 0)
        if abs(day_pct) >= rule["price_move_pct"]:
            direction = "UP" if day_pct > 0 else "DOWN"
            alerts.append(
                {
                    "ticker": ticker,
                    "type": "PRICE_MOVE",
                    "severity": "HIGH",
                    "message": f"{ticker} is {direction} {abs(day_pct):.1f}% today",
                    "time": stamp,
                }
            )

        curr = r.get("score", 0)
        prev = prev_scores.get(ticker, curr)
        if abs(curr - prev) >= rule["min_score_change"]:
            alerts.append(
                {
                    "ticker": ticker,
                    "type": "SIGNAL_CHANGE",
                    "severity": "HIGH",
                    "message": f"{ticker} signal score: {prev:+.1f} -> {curr:+.1f} ({r.get('signal', '?')})",
                    "time": stamp,
                }
            )

        earn = r.get("earn", {})
        days = earn.get("days_to_earnings") if isinstance(earn, Mapping) else None
        if days is not None and 0 <= days <= rule["earnings_days"]:
            alerts.append(
                {
                    "ticker": ticker,
                    "type": "EARNINGS",
                    "severity": "HIGH",
                    "message": f"{ticker} earnings in {days} day(s)",
                    "time": stamp,
                }
            )
    return alerts


def alert_email(alerts: Sequence[Mapping]) -> tuple[str, str]:
    """``(subject, body)`` for the short alert email."""
    tickers = sorted({a["ticker"] for a in alerts})
    subject = f"Stock Alert - {', '.join(tickers)}"
    body = "\n".join(f"- {a['message']}" for a in alerts)
    return subject, body


def load_scores(path: Path) -> dict[str, float]:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (OSError, ValueError):
        return {}


def save_scores(path: Path, results: Sequence[Mapping]) -> None:
    path.write_text(json.dumps({r["ticker"]: r.get("score", 0) for r in results}, indent=2), encoding="utf-8")


def save_alerts(path: Path, alerts: Sequence[Mapping]) -> None:
    path.write_text(json.dumps(list(alerts), indent=2), encoding="utf-8")
