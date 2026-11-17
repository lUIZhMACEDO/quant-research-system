"""EOD ingest pipeline.

Runs after the close to fetch, compute and store everything the research layer
reads from SQLite:

  1. OHLCV per ticker (yfinance), with data-quality checks
  2. Full-history technical indicators
  3. FRED macro snapshot
  4. Fundamentals snapshot
  5. Private-company proxy scores
  6. Data-quality summary
"""

from __future__ import annotations

import datetime as dt
import logging
import time
from collections.abc import Callable

import pandas as pd

from quant_research import storage
from quant_research.config import get_settings
from quant_research.ingest.fred import fetch_all_macro
from quant_research.ingest.fundamentals import fetch_fundamentals
from quant_research.ingest.prices import fetch_ohlcv
from quant_research.ingest.quality import check_ohlcv
from quant_research.ingest.universe import ingest_universe
from quant_research.signals.indicators import compute_indicator_frame
from quant_research.signals.proxies import build_space_economy_index, compute_proxy_scores

log = logging.getLogger(__name__)


def latest_snapshot(ind: pd.DataFrame) -> dict:
    """The last bar's momentum/RSI/vol values, used for proxy scores."""
    if ind.empty:
        return {}
    last = ind.iloc[-1]

    def val(col: str):
        v = last.get(col)
        return None if v is None or pd.isna(v) else float(v)

    return {
        "momentum_5d": val("momentum_5d"),
        "momentum_21d": val("momentum_21d"),
        "rsi_14": val("rsi_14"),
        "realized_vol": val("realized_vol_21d"),
    }


def run_pipeline(
    tickers: list[str] | None = None,
    db_path: str | None = None,
    fetch_prices: Callable[[str], pd.DataFrame | None] = fetch_ohlcv,
    fetch_macro: Callable[[], dict] = fetch_all_macro,
    fetch_fund: Callable[[str], dict] = fetch_fundamentals,
    today: dt.date | None = None,
    pause: float = 0.2,
    only: bool = False,
) -> dict:
    """Run the full EOD ingest. Fetchers are injectable so the pipeline can be tested offline.

    ``tickers`` are added to the default universe, or replace it when ``only`` is set.
    Returns a small summary dict (tickers stored, quality issue count).
    """
    today = today or dt.date.today()
    today_s = today.isoformat()
    universe = sorted(set(tickers)) if only and tickers else ingest_universe(tickers)

    con = storage.connect(db_path or get_settings().db_path)
    try:
        storage.init_schema(con)

        # 1-2. OHLCV + indicators
        prices_today: dict[str, dict] = {}
        stored = 0
        log.info("Fetching OHLCV for %d tickers...", len(universe))
        for ticker in universe:
            df = fetch_prices(ticker)
            issues = check_ohlcv(df, today)
            for issue in issues:
                storage.log_data_quality(con, ticker, issue, today_s)
            if df is None or df.empty:
                log.warning("No data for %s", ticker)
                continue
            storage.upsert_prices(con, df)
            ind = compute_indicator_frame(df)
            storage.upsert_indicators(con, ind)
            prices_today[ticker] = latest_snapshot(ind)
            stored += 1
            con.commit()
            if pause:
                time.sleep(pause)

        # 3. FRED macro
        log.info("Fetching FRED macro data...")
        storage.upsert_macro(con, fetch_macro(), today_s)
        con.commit()

        # 4. Fundamentals
        log.info("Fetching fundamentals...")
        for ticker in universe:
            storage.upsert_fundamentals(con, fetch_fund(ticker))
            if pause:
                time.sleep(pause)
        con.commit()

        # 5. Proxy scores
        log.info("Computing private company proxy scores...")
        scores: dict[str, float | None] = dict(compute_proxy_scores(prices_today))
        scores["space_economy_index"] = build_space_economy_index(prices_today)
        storage.log_proxy_scores(con, scores, today_s)
        con.commit()

        # 6. Quality summary
        issues = storage.count_quality_issues(con, today_s)
        if issues:
            log.warning("Data quality: %d issues logged for %s", issues, today_s)
        else:
            log.info("Data quality: clean run, no issues.")
    finally:
        con.close()

    log.info("Pipeline complete for %s.", today_s)
    return {"date": today_s, "tickers_stored": stored, "quality_issues": issues}


def main(argv: list[str] | None = None) -> None:
    """``python ingest.py [--tickers-file F] [--only] [--db PATH]``."""
    import argparse

    from quant_research.cli import add_ingest_args, run_ingest

    parser = argparse.ArgumentParser(prog="ingest.py", description="Fetch EOD data into SQLite.")
    add_ingest_args(parser)
    run_ingest(parser.parse_args(argv))


if __name__ == "__main__":
    main()
