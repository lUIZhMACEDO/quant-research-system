-- schema.sql — Quantitative Research System Database
-- SQLite, WAL mode (set in ingest.py: PRAGMA journal_mode=WAL)
-- Run via: con.executescript(open("schema.sql").read())
--
-- Tables:
--   prices              OHLCV + adjusted close, daily, per ticker
--   indicators          All computed technicals per ticker per date
--   fundamentals        Quarterly snapshots (P/E, EPS, revenue, etc.)
--   macro_daily         All macro series aligned to trading calendar
--   signal_log          Generated signals with features at time of signal
--   backtest_results    Strategy performance by ticker/date range
--   ml_features         Precomputed feature matrix ready for model training
--   ml_predictions      Walk-forward model outputs + confidence scores
--   earnings_calendar   Expected + actual EPS, surprise %, date
--   private_exposure    Public proxy relationships for private companies
--   private_valuation_log  Funding round history for private companies
--   proxy_scores        Daily synthetic exposure scores
--   data_quality        Fetch errors, missing bars, staleness per ticker

-- ---------------------------------------------------------------------------
-- prices
-- Always store adjusted close separately from raw — critical for backtesting
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS prices (
      id          INTEGER PRIMARY KEY AUTOINCREMENT,
      ticker      TEXT    NOT NULL,
      date        TEXT    NOT NULL,   -- ISO 8601: YYYY-MM-DD
    open        REAL,
      high        REAL,
      low         REAL,
      close       REAL,               -- adjusted close
    volume      REAL,
      UNIQUE(ticker, date)
  );
CREATE INDEX IF NOT EXISTS idx_prices_ticker_date ON prices(ticker, date);

-- ---------------------------------------------------------------------------
-- indicators
-- All technicals per ticker per date, computed in one vectorized pass
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS indicators (
      id                  INTEGER PRIMARY KEY AUTOINCREMENT,
      ticker              TEXT    NOT NULL,
      date                TEXT    NOT NULL,
      -- Momentum
    rsi_14              REAL,
      rsi_zscore_252      REAL,       -- z-score of RSI over rolling 252-day window
    macd                REAL,
      macd_signal         REAL,
      macd_hist           REAL,
      -- Volatility / Bands
    bb_upper            REAL,
      bb_lower            REAL,
      bb_mid              REAL,
      bb_pct              REAL,       -- 0 = at lower band, 1 = at upper band
    atr_14              REAL,
      atr_pct             REAL,       -- ATR / close, normalized
    realized_vol_21d    REAL,       -- annualized 21-day realized vol
    -- Trend
    sma_50              REAL,
      sma_200             REAL,
      ema_20              REAL,
      golden_cross        INTEGER,    -- 1 = SMA50 > SMA200, 0 = otherwise
    -- Price momentum
    momentum_5d         REAL,
      momentum_21d        REAL,
      momentum_63d        REAL,
      momentum_252d       REAL,
      -- Volume
    vol_zscore_20d      REAL,
      -- Regime
    hurst_64            REAL,       -- H>0.5 trending, H<0.5 mean-reverting
    -- Cross-sectional ranks (filled at portfolio level)
    rsi_rank            REAL,       -- percentile rank vs universe on this date
    mom_rank            REAL,
      UNIQUE(ticker, date)
  );
CREATE INDEX IF NOT EXISTS idx_ind_ticker_date ON indicators(ticker, date);

-- ---------------------------------------------------------------------------
-- fundamentals
-- Quarterly snapshot per ticker — use latest available on any given date
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fundamentals (
      id                  INTEGER PRIMARY KEY AUTOINCREMENT,
      ticker              TEXT    NOT NULL,
      date                TEXT    NOT NULL,   -- date fetched
    pe_ttm              REAL,
      pe_forward          REAL,
      pb                  REAL,               -- price-to-book
    ps_ttm              REAL,               -- price-to-sales TTM
    ev_ebitda           REAL,
      ev_revenue          REAL,
      fcf_yield           REAL,               -- FCF / market cap
    earnings_growth_yoy REAL,
      revenue_growth_yoy  REAL,
      debt_to_equity      REAL,
      current_ratio       REAL,
      roe                 REAL,               -- return on equity
    profit_margin       REAL,
      analyst_target_price REAL,
      analyst_rating      REAL,               -- 1=Strong Buy, 5=Sell (consensus)
    num_analysts        INTEGER,
      short_pct_float     REAL,
      insider_pct         REAL,
      UNIQUE(ticker, date)
  );
CREATE INDEX IF NOT EXISTS idx_fund_ticker_date ON fundamentals(ticker, date);

-- ---------------------------------------------------------------------------
-- macro_daily
-- All FRED series + derived macro metrics, aligned to trading calendar
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS macro_daily (
      id                  INTEGER PRIMARY KEY AUTOINCREMENT,
      date                TEXT    NOT NULL UNIQUE,
      -- Treasury yields
    treasury_3m         REAL,
      treasury_2y         REAL,
      treasury_5y         REAL,
      treasury_10y        REAL,
      treasury_30y        REAL,
      -- Yield curve
    spread_10y_2y       REAL,               -- FRED T10Y2Y
    spread_10y_3m       REAL,               -- FRED T10Y3M (recession indicator)
    curve_slope_10y_3m  REAL,               -- derived: 10y - 3m
    curve_slope_10y_2y  REAL,               -- derived: 10y - 2y
    -- Credit
    hy_spread           REAL,               -- FRED BAMLH0A0HYM2 (HY OAS)
    ig_spread           REAL,               -- FRED BAMLC0A0CM (IG OAS)
    hy_ig_differential  REAL,               -- derived: HY - IG
    -- Dollar & volatility
    dxy_broad           REAL,               -- FRED DTWEXBGS
    vix                 REAL,
      -- Economic indicators (monthly, forward-filled to daily)
    unemployment        REAL,
      cpi                 REAL,
      m2_money_supply     REAL,
      fed_funds_rate      REAL,
      mortgage_30y        REAL
  );
CREATE INDEX IF NOT EXISTS idx_macro_date ON macro_daily(date);

-- ---------------------------------------------------------------------------
-- signal_log
-- Every generated signal with the feature vector at time of generation.
-- Used for walk-forward validation and feature importance analysis.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS signal_log (
      id                  INTEGER PRIMARY KEY AUTOINCREMENT,
      date                TEXT    NOT NULL,
      ticker              TEXT    NOT NULL,
      strategy            TEXT,               -- e.g. 'rsi_macd', 'golden_cross'
    signal_direction    TEXT,               -- 'long', 'short', 'neutral'
    composite_score     REAL,               -- combined signal score 0-100
    confidence          REAL,               -- ML model probability if available
    -- Feature snapshot at signal time
    rsi_14              REAL,
      rsi_zscore          REAL,
      macd_hist           REAL,
      bb_pct              REAL,
      momentum_5d         REAL,
      momentum_21d        REAL,
      realized_vol        REAL,
      hurst               REAL,
      golden_cross        INTEGER,
      pe_forward          REAL,
      ev_ebitda           REAL,
      hy_spread           REAL,
      spread_10y_2y       REAL,
      -- Forward returns (filled in retrospectively by backtest)
    fwd_return_5d       REAL,
      fwd_return_21d      REAL,
      fwd_return_63d      REAL,
      fwd_sharpe_21d      REAL,               -- risk-adjusted forward return
    UNIQUE(ticker, date, strategy)
  );
CREATE INDEX IF NOT EXISTS idx_sig_date ON signal_log(date);
CREATE INDEX IF NOT EXISTS idx_sig_ticker ON signal_log(ticker);

-- ---------------------------------------------------------------------------
-- backtest_results
-- Strategy performance summary per ticker per date range.
-- Always benchmark against SPY buy-and-hold Sharpe.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS backtest_results (
      id                  INTEGER PRIMARY KEY AUTOINCREMENT,
      run_date            TEXT    NOT NULL,
      strategy            TEXT    NOT NULL,
      ticker              TEXT,               -- NULL = portfolio-level result
    start_date          TEXT,
      end_date            TEXT,
      total_trades        INTEGER,
      win_rate            REAL,
      avg_return_per_trade REAL,
      sharpe_ratio        REAL,
      max_drawdown        REAL,
      -- Benchmark comparison
    spy_sharpe          REAL,
      alpha_vs_spy        REAL,               -- strategy Sharpe - SPY Sharpe
    -- Cost assumptions
    tx_cost_pct         REAL DEFAULT 0.0005,  -- 0.05% per trade
    slippage_model      TEXT DEFAULT 'next_open'
  );

-- ---------------------------------------------------------------------------
-- ml_features
-- Precomputed feature matrix — ready for model training.
-- One row per ticker per date with all features + target.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ml_features (
      id                  INTEGER PRIMARY KEY AUTOINCREMENT,
      ticker              TEXT    NOT NULL,
      date                TEXT    NOT NULL,
      -- Technical features
    rsi_14              REAL,
      rsi_zscore_252      REAL,
      macd_hist           REAL,
      bb_pct              REAL,
      momentum_5d         REAL,
      momentum_21d        REAL,
      momentum_63d        REAL,
      momentum_252d       REAL,
      vol_zscore_20d      REAL,
      realized_vol_21d    REAL,
      hurst_64            REAL,
      golden_cross        INTEGER,
      atr_pct             REAL,
      -- Lagged features
    rsi_lag1            REAL,
      rsi_5d_change       REAL,
      momentum_lag5       REAL,
      -- Fundamental features
    pe_forward          REAL,
      ev_ebitda           REAL,
      fcf_yield           REAL,
      earnings_growth_yoy REAL,
      -- Macro features
    spread_10y_2y       REAL,
      hy_spread           REAL,
      vix                 REAL,
      -- Cross-sectional ranks (position in universe)
    rsi_rank            REAL,
      mom_rank            REAL,
      -- Target variables
    fwd_return_5d       REAL,               -- raw forward return
    fwd_return_21d      REAL,
      fwd_sharpe_21d      REAL,               -- risk-adjusted (return / realized_vol)
    fwd_quintile_21d    INTEGER,            -- cross-sectional quintile (1=bottom, 5=top)
    UNIQUE(ticker, date)
  );

-- ---------------------------------------------------------------------------
-- ml_predictions
-- Walk-forward model output per ticker per date.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ml_predictions (
      id                  INTEGER PRIMARY KEY AUTOINCREMENT,
      date                TEXT    NOT NULL,
      ticker              TEXT    NOT NULL,
      model_name          TEXT,               -- 'lgbm', 'ridge', 'ensemble'
    train_window_start  TEXT,               -- walk-forward window
    train_window_end    TEXT,
      predicted_return    REAL,
      predicted_quintile  INTEGER,
      confidence          REAL,               -- model probability / certainty
    feature_importance  TEXT,               -- JSON: {feature: importance_score}
    UNIQUE(ticker, date, model_name)
  );

-- ---------------------------------------------------------------------------
-- earnings_calendar
-- Expected vs actual EPS, surprise %, date
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS earnings_calendar (
      id                  INTEGER PRIMARY KEY AUTOINCREMENT,
      ticker              TEXT    NOT NULL,
      report_date         TEXT    NOT NULL,
      period              TEXT,               -- 'Q1 2025', etc.
    eps_estimate        REAL,
      eps_actual          REAL,
      eps_surprise_pct    REAL,               -- (actual - estimate) / abs(estimate)
    revenue_estimate    REAL,
      revenue_actual      REAL,
      rev_surprise_pct    REAL,
      UNIQUE(ticker, report_date)
  );

-- ---------------------------------------------------------------------------
-- private_exposure
-- Public proxy relationships for private companies
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS private_exposure (
      id                  INTEGER PRIMARY KEY AUTOINCREMENT,
      private_company     TEXT    NOT NULL,   -- 'Anthropic', 'SpaceX', etc.
    public_ticker       TEXT    NOT NULL,   -- 'AMZN', 'GOOG', etc.
    exposure_type       TEXT,               -- 'investor', 'customer', 'infrastructure', 'competitor_comp'
    ownership_pct       REAL,               -- known stake pct (e.g. 0.27 for Amazon in Anthropic)
    relevance_score     REAL,               -- 0.0-1.0 proxy weight
    notes               TEXT,
      last_updated        TEXT,
      UNIQUE(private_company, public_ticker)
  );

-- ---------------------------------------------------------------------------
-- private_valuation_log
-- Funding round history for private companies — update manually on new rounds
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS private_valuation_log (
      id                  INTEGER PRIMARY KEY AUTOINCREMENT,
      private_company     TEXT    NOT NULL,
      valuation_usd       REAL    NOT NULL,
      round_name          TEXT,               -- 'Series F', 'Tender Offer', etc.
    date_reported       TEXT,
      source              TEXT
  );

-- ---------------------------------------------------------------------------
-- proxy_scores
-- Daily synthetic exposure scores for tracked private companies
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS proxy_scores (
      id                  INTEGER PRIMARY KEY AUTOINCREMENT,
      date                TEXT    NOT NULL,
      private_company     TEXT    NOT NULL,   -- or 'space_economy_index'
    proxy_score         REAL,               -- weighted momentum score
    UNIQUE(date, private_company)
  );

-- ---------------------------------------------------------------------------
-- data_quality
-- Logs any fetch errors, missing bars, staleness per ticker per date
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS data_quality (
      id                  INTEGER PRIMARY KEY AUTOINCREMENT,
      date                TEXT    NOT NULL,
      ticker              TEXT    NOT NULL,
      issue               TEXT    NOT NULL    -- 'no_ohlcv', 'stale_2025-03-01', etc.
);
