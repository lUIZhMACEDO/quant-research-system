"""SQLite access: connection setup, schema creation and idempotent writes.

All writes use ``INSERT OR IGNORE`` against the tables' UNIQUE constraints, so
re-running the pipeline for a date never duplicates rows. Column names are
checked against the live table before building SQL, which keeps unexpected
DataFrame columns from ever reaching a statement.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Mapping
from importlib import resources
from pathlib import Path

import pandas as pd

INDICATOR_COLUMNS: list[str] = [
    "ticker",
    "date",
    "rsi_14",
    "rsi_zscore_252",
    "macd",
    "macd_signal",
    "macd_hist",
    "bb_pct",
    "sma_50",
    "sma_200",
    "ema_20",
    "golden_cross",
    "atr_14",
    "atr_pct",
    "realized_vol_21d",
    "momentum_5d",
    "momentum_21d",
    "momentum_63d",
    "momentum_252d",
    "vol_zscore_20d",
    "hurst_64",
]

PRICE_COLUMNS: list[str] = ["ticker", "date", "open", "high", "low", "close", "volume"]


def connect(db_path: str | Path) -> sqlite3.Connection:
    """Open the database in WAL mode with foreign keys enforced."""
    con = sqlite3.connect(str(db_path))
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    return con


def schema_sql() -> str:
    return resources.files("quant_research.storage").joinpath("schema.sql").read_text(encoding="utf-8")


def init_schema(con: sqlite3.Connection) -> None:
    """Create all tables and indexes if they don't exist."""
    con.executescript(schema_sql())
    con.commit()


def _table_columns(con: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in con.execute(f"PRAGMA table_info({table})")}


def _insert_or_ignore(con: sqlite3.Connection, table: str, rows: Iterable[Mapping]) -> int:
    """Insert rows, skipping any that collide with a UNIQUE constraint. Returns rows inserted."""
    rows = list(rows)
    if not rows:
        return 0
    allowed = _table_columns(con, table)
    if not allowed:
        raise ValueError(f"Unknown table: {table}")
    cols = [c for c in rows[0] if c in allowed]
    unknown = set(rows[0]) - allowed
    if unknown:
        raise ValueError(f"Columns not in {table}: {sorted(unknown)}")
    placeholders = ", ".join("?" for _ in cols)
    sql = f"INSERT OR IGNORE INTO {table} ({', '.join(cols)}) VALUES ({placeholders})"
    before = con.total_changes
    con.executemany(sql, [tuple(_to_sql_value(r.get(c)) for c in cols) for r in rows])
    return con.total_changes - before


def _to_sql_value(value):
    """Convert numpy/pandas scalars and NaN to plain Python types sqlite3 understands."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        return value.item()
    return value


def _frame_rows(df: pd.DataFrame, columns: list[str]) -> list[dict]:
    out = df.copy()
    out["date"] = [d.date().isoformat() if hasattr(d, "date") else str(d) for d in out.index]
    present = [c for c in columns if c in out.columns]
    return out[present].to_dict(orient="records")


def upsert_prices(con: sqlite3.Connection, df: pd.DataFrame) -> int:
    """Store OHLCV rows. ``df`` is indexed by date with a ``ticker`` column."""
    return _insert_or_ignore(con, "prices", _frame_rows(df, PRICE_COLUMNS))


def upsert_indicators(con: sqlite3.Connection, df: pd.DataFrame) -> int:
    return _insert_or_ignore(con, "indicators", _frame_rows(df, INDICATOR_COLUMNS))


def upsert_macro(con: sqlite3.Connection, macro: Mapping[str, float | None], date: str) -> int:
    return _insert_or_ignore(con, "macro_daily", [{"date": date, **macro}])


def upsert_fundamentals(con: sqlite3.Connection, fund: Mapping) -> int:
    return _insert_or_ignore(con, "fundamentals", [dict(fund)])


def log_proxy_scores(con: sqlite3.Connection, scores: Mapping[str, float | None], date: str) -> int:
    rows = [{"date": date, "private_company": k, "proxy_score": v} for k, v in scores.items()]
    return _insert_or_ignore(con, "proxy_scores", rows)


def log_data_quality(con: sqlite3.Connection, ticker: str, issue: str, date: str) -> int:
    return _insert_or_ignore(con, "data_quality", [{"date": date, "ticker": ticker, "issue": issue}])


def count_quality_issues(con: sqlite3.Connection, date: str) -> int:
    return con.execute("SELECT COUNT(*) FROM data_quality WHERE date = ?", (date,)).fetchone()[0]
