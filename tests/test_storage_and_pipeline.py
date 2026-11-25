"""SQLite layer and the end-to-end ingest pipeline with fake fetchers (no network)."""

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from conftest import make_ohlcv
from quant_research import storage
from quant_research.ingest.pipeline import run_pipeline


@pytest.fixture
def con(tmp_path):
    c = storage.connect(tmp_path / "test.db")
    storage.init_schema(c)
    yield c
    c.close()


def _prices(n=30, ticker="SPY"):
    df = make_ohlcv(np.linspace(100, 110, n), start="2026-10-01")
    df.insert(0, "ticker", ticker)
    return df


def test_schema_creates_all_tables(con):
    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    expected = {
        "prices",
        "indicators",
        "fundamentals",
        "macro_daily",
        "signal_log",
        "backtest_results",
        "ml_features",
        "ml_predictions",
        "earnings_calendar",
        "private_exposure",
        "private_valuation_log",
        "proxy_scores",
        "data_quality",
    }
    assert expected <= tables


def test_wal_mode_enabled(con):
    assert con.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"


def test_upsert_prices_is_idempotent(con):
    df = _prices()
    assert storage.upsert_prices(con, df) == 30
    assert storage.upsert_prices(con, df) == 0  # UNIQUE(ticker, date) + INSERT OR IGNORE
    assert con.execute("SELECT COUNT(*) FROM prices").fetchone()[0] == 30
    first_date = con.execute("SELECT MIN(date) FROM prices").fetchone()[0]
    assert first_date == "2026-10-01"


def test_nan_is_stored_as_null(con):
    df = _prices()
    df["rsi_14"] = np.nan
    storage.upsert_indicators(con, df)
    assert con.execute("SELECT COUNT(*) FROM indicators WHERE rsi_14 IS NULL").fetchone()[0] == 30


def test_unknown_column_is_rejected(con):
    with pytest.raises(ValueError, match="Columns not in fundamentals"):
        storage.upsert_fundamentals(con, {"ticker": "X", "date": "2026-01-01", "evil); DROP TABLE x;--": 1})


def test_numpy_scalars_are_converted(con):
    storage.upsert_macro(con, {"vix": np.float64(15.5), "treasury_10y": None}, "2026-11-13")
    row = con.execute("SELECT vix, treasury_10y FROM macro_daily").fetchone()
    assert row == (15.5, None)


def test_quality_log_and_count(con):
    storage.log_data_quality(con, "SPY", "no_ohlcv", "2026-11-13")
    storage.log_data_quality(con, "QQQ", "stale_2026-11-01", "2026-11-13")
    assert storage.count_quality_issues(con, "2026-11-13") == 2
    assert storage.count_quality_issues(con, "2026-11-12") == 0


def test_run_pipeline_offline(tmp_path):
    today = dt.date(2026, 11, 13)
    n = 300
    idx_end = pd.Timestamp(today)

    def fake_prices(ticker):
        if ticker == "VIX":  # simulate a ticker the provider can't serve
            return None
        close = np.linspace(100, 130, n) * (1 + 0.001 * (sum(map(ord, ticker)) % 7))
        df = make_ohlcv(close, start=str((idx_end - pd.tseries.offsets.BDay(n - 1)).date()))
        df.insert(0, "ticker", ticker)
        return df

    summary = run_pipeline(
        tickers=["SPY"],
        db_path=tmp_path / "quant.db",
        today=today,
        pause=0,
        fetch_prices=fake_prices,
        fetch_macro=lambda: {"treasury_10y": 4.1, "vix": 15.0},
        fetch_fund=lambda t: {"ticker": t, "date": today.isoformat(), "pe_ttm": 20.0},
    )

    con = storage.connect(tmp_path / "quant.db")
    try:
        assert summary["quality_issues"] == 1
        assert con.execute("SELECT issue FROM data_quality WHERE ticker='VIX'").fetchone()[0] == "no_ohlcv"
        assert con.execute("SELECT COUNT(DISTINCT ticker) FROM prices").fetchone()[0] == summary["tickers_stored"]
        assert con.execute("SELECT COUNT(*) FROM indicators WHERE hurst_64 IS NOT NULL").fetchone()[0] > 0
        assert con.execute("SELECT vix FROM macro_daily").fetchone()[0] == 15.0
        companies = {r[0] for r in con.execute("SELECT private_company FROM proxy_scores")}
        assert {"Anthropic", "SpaceX", "OpenAI", "space_economy_index"} <= companies
    finally:
        con.close()

    # Re-running the same day adds no duplicate rows.
    before = summary["tickers_stored"]
    again = run_pipeline(
        tickers=["SPY"],
        db_path=tmp_path / "quant.db",
        today=today,
        pause=0,
        fetch_prices=fake_prices,
        fetch_macro=lambda: {},
        fetch_fund=lambda t: {"ticker": t, "date": today.isoformat()},
    )
    assert again["tickers_stored"] == before
    con = storage.connect(tmp_path / "quant.db")
    try:
        assert con.execute("SELECT COUNT(*) FROM prices WHERE ticker='SPY'").fetchone()[0] == n
    finally:
        con.close()
