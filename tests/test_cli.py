"""The quick-start commands in the README, run against the committed examples/ files."""

import datetime as dt
from pathlib import Path

import numpy as np
import pytest

from conftest import make_ohlcv
from quant_research import storage
from quant_research.cli import analyze_prices, load_price_csv, main, read_tickers
from quant_research.ingest.pipeline import run_pipeline

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def test_example_csv_matches_readme_output(capsys):
    assert main(["analyze", str(EXAMPLES / "sample_prices.csv"), "--ticker", "SAMPLE"]) == 0
    out = capsys.readouterr().out
    assert out.splitlines()[0] == "SAMPLE  last bar 2026-10-15  close 101.81"
    assert "RSI(14)      19.2 (OVERSOLD)" in out
    assert "Screen       Bollinger Band Mean Reversion" in out
    assert "Score        +1.5 -> TRIM" in out


def test_analyze_prices_structure():
    result = analyze_prices(load_price_csv(EXAMPLES / "sample_prices.csv"))
    assert result["strategy"] == "BB_MEAN_REVERSION"
    assert result["score"]["breakdown"]["rsi"] == 2.0


def test_load_price_csv_rejects_missing_columns(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("Date,Close\n2026-01-02,100\n")
    with pytest.raises(ValueError, match="missing columns"):
        load_price_csv(bad)


def test_read_tickers_skips_comments_and_blanks():
    assert read_tickers(str(EXAMPLES / "tickers.txt")) == ["SPY", "AAPL", "MSFT", "NVDA"]
    assert read_tickers(None) == []


def test_only_flag_limits_the_universe(tmp_path):
    fetched = []

    def fake_prices(ticker):
        fetched.append(ticker)
        df = make_ohlcv(np.linspace(100, 120, 260), start="2025-11-20")
        df.insert(0, "ticker", ticker)
        return df

    run_pipeline(
        tickers=["MSFT", "AAPL"],
        only=True,
        db_path=tmp_path / "q.db",
        today=dt.date(2026, 11, 17),
        pause=0,
        fetch_prices=fake_prices,
        fetch_macro=lambda: {},
        fetch_fund=lambda t: {"ticker": t, "date": "2026-11-17"},
    )
    assert fetched == ["AAPL", "MSFT"]
    con = storage.connect(tmp_path / "q.db")
    try:
        assert con.execute("SELECT COUNT(DISTINCT ticker) FROM prices").fetchone()[0] == 2
    finally:
        con.close()
