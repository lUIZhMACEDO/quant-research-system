"""FRED macro series: fetch, parse, and derive spreads.

Parsing is separated from the HTTP call so it can be unit-tested against a
fixture CSV with no network access.
"""

from __future__ import annotations

import datetime as dt
import io
import logging
import time
from collections.abc import Callable

import pandas as pd
import requests

from quant_research.ingest.universe import FRED_SERIES

log = logging.getLogger(__name__)

FRED_BASE = "https://fred.stlouisfed.org/graph/fredgraph.csv"
REQUEST_TIMEOUT = 20


def parse_fred_csv(text: str) -> float | None:
    """Return the latest non-missing observation in a FRED ``fredgraph.csv`` payload.

    FRED marks missing observations with ``"."``. The date column has been called
    both ``DATE`` and ``observation_date`` over time, so the first column is used
    whatever its name.
    """
    if not text or not text.strip():
        return None
    df = pd.read_csv(io.StringIO(text), na_values=["."])
    if df.shape[1] < 2:
        return None
    values = pd.to_numeric(df.iloc[:, 1], errors="coerce").dropna()
    if values.empty:
        return None
    return float(values.iloc[-1])


def fetch_fred_series(series_id: str, lookback_days: int = 30, session: requests.Session | None = None) -> float | None:
    """Fetch the latest value for one FRED series. Returns ``None`` on any failure."""
    since = (dt.date.today() - dt.timedelta(days=lookback_days)).isoformat()
    http = session or requests
    try:
        resp = http.get(FRED_BASE, params={"id": series_id, "cosd": since}, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return parse_fred_csv(resp.text)
    except Exception as exc:  # network, HTTP or parse errors all degrade to "no value"
        log.warning("FRED fetch failed for %s: %s", series_id, exc)
        return None


def derive_macro_spreads(values: dict[str, float | None]) -> dict[str, float]:
    """Curve slopes and the HY-IG differential, computed only when both legs exist."""
    derived: dict[str, float] = {}
    t10, t3m, t2 = values.get("treasury_10y"), values.get("treasury_3m"), values.get("treasury_2y")
    if t10 is not None and t3m is not None:
        derived["curve_slope_10y_3m"] = round(t10 - t3m, 4)
    if t10 is not None and t2 is not None:
        derived["curve_slope_10y_2y"] = round(t10 - t2, 4)
    hy, ig = values.get("hy_spread"), values.get("ig_spread")
    if hy is not None and ig is not None:
        derived["hy_ig_differential"] = round(hy - ig, 4)
    return derived


def fetch_all_macro(
    fetch: Callable[[str], float | None] = fetch_fred_series, delay: float = 0.3
) -> dict[str, float | None]:
    """Fetch every series in :data:`FRED_SERIES` plus derived spreads (label -> value)."""
    result: dict[str, float | None] = {}
    for series_id, label in FRED_SERIES.items():
        result[label] = fetch(series_id)
        if delay:
            time.sleep(delay)  # be polite to FRED
    result.update(derive_macro_spreads(result))
    return result
