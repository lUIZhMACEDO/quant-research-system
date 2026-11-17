"""Command line: ``python -m quant_research analyze <csv>`` and ``python -m quant_research ingest``.

``analyze`` runs one price CSV through the signal code with no network access,
which is the quickest way to see what the screens and score do.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

from quant_research.signals.scoring import compute_signal_score
from quant_research.signals.screens import STRATEGY_NAMES, detect_strategy
from quant_research.signals.technicals import technical_snapshot

PRICE_COLUMNS = ["Open", "High", "Low", "Close", "Volume"]


def load_price_csv(path: str | Path) -> pd.DataFrame:
    """Read a daily OHLCV CSV with a ``Date`` column (the format yfinance exports)."""
    df = pd.read_csv(path, parse_dates=["Date"], index_col="Date")
    missing = [c for c in PRICE_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"{path}: missing columns {missing}")
    return df[PRICE_COLUMNS].sort_index()


def analyze_prices(df: pd.DataFrame, ticker: str = "SAMPLE") -> dict:
    """Technical snapshot, first screen that fires, and the technicals-only composite score."""
    tech = technical_snapshot(df)
    strategy = detect_strategy(tech, analyst={}, earnings={})
    score = compute_signal_score(
        ticker, tech, financials={}, analyst_data={}, news=None, price=float(df["Close"].iloc[-1])
    )
    return {
        "ticker": ticker,
        "last_date": df.index[-1].date().isoformat(),
        "close": float(df["Close"].iloc[-1]),
        "tech": tech,
        "strategy": strategy,
        "score": score,
    }


def format_analysis(result: dict) -> str:
    t, s = result["tech"], result["score"]
    lines = [
        f"{result['ticker']}  last bar {result['last_date']}  close {result['close']:.2f}",
        f"  RSI(14)      {t['rsi']} ({t['rsi_label']})",
        f"  MACD         {t['macd_label']}",
        f"  Bollinger    {t['bb_label']}",
        f"  EMA 20/50    {t['ema_label']}",
        f"  Volume       {t['vol_label']}",
        f"  ATR stop     {t['atr_stop']}   ATR target {t['atr_target']}",
        f"  Screen       {STRATEGY_NAMES[result['strategy']]}",
        f"  Score        {s['score']:+.1f} -> {s['signal']}",
        f"  Why          {s['reasoning']}",
    ]
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m quant_research")
    sub = parser.add_subparsers(dest="command", required=True)

    a = sub.add_parser("analyze", help="run one price CSV through the screens (offline)")
    a.add_argument("csv", help="CSV with Date,Open,High,Low,Close,Volume columns")
    a.add_argument("--ticker", default=None, help="label for the output (default: file name)")

    i = sub.add_parser("ingest", help="fetch EOD data into SQLite")
    add_ingest_args(i)
    return parser


def add_ingest_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--tickers-file", help="text file with one ticker per line")
    parser.add_argument(
        "--only", action="store_true", help="fetch only the tickers in --tickers-file, not the default universe"
    )
    parser.add_argument("--db", help="SQLite path (default: DB_PATH or quant.db)")


def read_tickers(path: str | None) -> list[str]:
    if not path:
        return []
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [ln.strip().upper() for ln in lines if ln.strip() and not ln.lstrip().startswith("#")]


def run_ingest(args: argparse.Namespace) -> None:
    from quant_research.ingest.pipeline import run_pipeline

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    summary = run_pipeline(tickers=read_tickers(args.tickers_file), db_path=args.db, only=args.only)
    print(
        f"stored {summary['tickers_stored']} tickers for {summary['date']}, "
        f"{summary['quality_issues']} data-quality issues"
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "analyze":
        ticker = args.ticker or Path(args.csv).stem.upper()
        print(format_analysis(analyze_prices(load_price_csv(args.csv), ticker)))
    elif args.command == "ingest":
        run_ingest(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
