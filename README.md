# Quantitative Research System

> v3.1.0 — Multi-factor signal scoring, walk-forward validation, FRED macro, fundamentals, private company exposure tracking, EOD data pipeline, and live Streamlit dashboard.
>
> ---
>
> ## What This Is
>
> A quantitative equity research platform that ingests 5 years of daily price data, computes a broad set of technical and fundamental features, scores each ticker across multiple strategies, and delivers a daily email report. The system is designed around proper quant research principles: vectorized indicator computation, walk-forward cross-validation (not a single train/test split), transaction cost modeling, benchmark-adjusted Sharpe ratios, and a normalized SQLite data store with WAL mode.
>
> It also tracks **synthetic exposure to private companies** (Anthropic, SpaceX, OpenAI, xAI, Stripe) using weighted public proxy stocks, so you can monitor private-market sentiment through liquid instruments.
>
> ---
>
> ## Architecture
>
> ```
> quant-research-system/
> ├── ingest.py                       # EOD data pipeline (run at 4:05 PM ET)
> ├── schema.sql                      # Full SQLite schema (13 tables)
> ├── main.py                         # Signal engine + email report builder
> ├── app.py                          # Streamlit dashboard
> ├── requirements.txt
> ├── packages.txt
> ├── .streamlit/config.toml
> └── .github/workflows/daily-report.yml
> ```
>
> **Data flow:**
> ```
> 4:05 PM ET  ingest.py runs
>             ├── Fetch OHLCV (yfinance / Tiingo)
>             ├── Fetch FRED macro (16 series)
>             ├── Vectorized technicals (full 5-year series)
>             ├── Fundamentals snapshot
>             ├── Compute private company proxy scores
>             ├── Append to signal_log
>             ├── Re-run walk-forward ML predictions
>             └── Data quality checks → data_quality table
>
> app.py / main.py read from quant.db
> ```
>
> ---
>
> ## Database Schema (13 Tables)
>
> | Table | Description |
> |---|---|
> | `prices` | OHLCV + adjusted close, daily per ticker |
> | `indicators` | All technicals per ticker per date (vectorized) |
> | `fundamentals` | P/E, EV/EBITDA, FCF yield, ROE, analyst ratings |
> | `macro_daily` | 16 FRED series + derived yield curve metrics |
> | `signal_log` | Every signal with full feature vector at generation time |
> | `backtest_results` | Strategy Sharpe, drawdown, win rate, alpha vs SPY |
> | `ml_features` | Precomputed feature matrix for model training |
> | `ml_predictions` | Walk-forward predictions per ticker per model |
> | `earnings_calendar` | EPS estimates, actuals, surprise % |
> | `private_exposure` | Public proxy relationships for private companies |
> | `private_valuation_log` | Funding round history (manual updates) |
> | `proxy_scores` | Daily synthetic exposure scores |
> | `data_quality` | Fetch errors, stale bars, missing tickers |
>
> SQLite is run in **WAL mode** (`PRAGMA journal_mode=WAL`) for better concurrent read performance and crash safety.
>
> ---
>
> ## Technical Indicators
>
> All indicators are computed in a **single vectorized pass** over the full 5-year series, fixing the O(n²) row-by-row bug in the original implementation.
>
> | Indicator | Description |
> |---|---|
> | RSI-14 | 14-period Relative Strength Index |
> | RSI z-score | RSI normalized over rolling 252-day window |
> | MACD / Signal / Hist | 12/26/9 MACD |
> | Bollinger Bands | 20-period, 2 std dev; `bb_pct` = position in band |
> | SMA 50 / 200 | Simple moving averages |
> | EMA 20 | Exponential moving average |
> | Golden / Death Cross | SMA50 vs SMA200 crossover signal |
> | ATR-14 | Average True Range (absolute + normalized as % of close) |
> | Realized Vol (21d) | Annualized 21-day realized volatility |
> | Momentum | 5d / 21d / 63d / 252d price change |
> | Volume z-score | Volume vs 20-day rolling mean |
> | Hurst Exponent | R/S analysis on 64-bar windows — H>0.5 trending, H<0.5 mean-reverting |
> | Cross-sectional rank | RSI rank and momentum rank vs full universe on each date |
>
> ---
>
> ## Fundamental Data
>
> | Metric | Source |
> |---|---|
> | P/E TTM + Forward P/E | yfinance .info (upgrade: Tiingo / IEX) |
> | Price/Book, Price/Sales | yfinance .info |
> | EV/EBITDA, EV/Revenue | yfinance .info |
> | FCF Yield | Computed: Free Cash Flow / Market Cap |
> | Earnings + Revenue Growth YoY | yfinance .info |
> | Debt/Equity, Current Ratio | yfinance .info |
> | ROE, Profit Margin | yfinance .info |
> | Analyst Target Price + Rating | yfinance .info (consensus 1-5 scale) |
> | Short % of Float | yfinance .info |
> | Insider Ownership % | yfinance .info |
>
> ---
>
> ## FRED Macro Data (16 Series)
>
> Fetched daily from the Federal Reserve Economic Data API (no key required for public series).
>
> | Series | Label | Notes |
> |---|---|---|
> | DGS3MO | treasury_3m | 3-month Treasury yield |
> | DGS2 | treasury_2y | 2-year Treasury yield |
> | DGS5 | treasury_5y | 5-year Treasury yield |
> | DGS10 | treasury_10y | 10-year Treasury yield |
> | DGS30 | treasury_30y | 30-year Treasury yield |
> | T10Y2Y | spread_10y_2y | Classic yield curve spread |
> | T10Y3M | spread_10y_3m | Recession-predictive spread |
> | BAMLH0A0HYM2 | hy_spread | High-yield OAS credit spread |
> | BAMLC0A0CM | ig_spread | Investment-grade OAS spread |
> | DTWEXBGS | dxy_broad | Broad dollar index |
> | VIXCLS | vix | CBOE VIX |
> | UNRATE | unemployment | Monthly unemployment rate |
> | CPIAUCSL | cpi | CPI (monthly) |
> | M2SL | m2_money_supply | M2 money supply |
> | FEDFUNDS | fed_funds_rate | Effective fed funds rate |
> | MORTGAGE30US | mortgage_30y | 30-year mortgage rate |
>
> **Derived metrics computed daily:** `curve_slope_10y_3m`, `curve_slope_10y_2y`, `hy_ig_differential`
>
> ---
>
> ## Private Company Exposure Tracking
>
> Since Anthropic, SpaceX, OpenAI, xAI, and Stripe are private, the system builds **synthetic exposure scores** from weighted public proxy stocks. Scores update daily as part of the ingest pipeline.
>
> ### Tracked Companies & Known Valuations
>
> | Company | Last Valuation | Round | Date |
> |---|---|---|---|
> | Anthropic | $61.5B | Series F | Mar 2025 |
> | SpaceX | $350B | Tender Offer | Dec 2024 |
> | OpenAI | $300B | Series F+ | Jan 2025 |
> | xAI | $50B | Series B | Nov 2024 |
> | Stripe | $91.5B | Secondary | Oct 2024 |
>
> ### Proxy Tickers
>
> **Anthropic** — AMZN (27% stake), GOOG (10% stake), NVDA (30% infra weight), MSFT (15% sector comp), ARM (18% chip architecture)
>
> **SpaceX** — RKLB (35% comp), ASTS (25% satellite comp), LUNR (20% NASA adjacency), KTOS (20% defense/satellite)
>
> **OpenAI** — MSFT (60% revenue-share weight), NVDA (30% GPU dependency), ARM (10%)
>
> **Space Economy Index** — Equal-weight RKLB + ASTS + LUNR + KTOS daily momentum score
>
> Valuations are stored in `private_valuation_log` and updated manually when new funding rounds close.
>
> ---
>
> ## Trading Strategies
>
> Five strategies run simultaneously per ticker. Each produces a signal score; scores combine into a composite rating.
>
> | Strategy | Logic |
> |---|---|
> | RSI + MACD | RSI oversold + MACD histogram turning positive |
> | Bollinger Band Mean Reversion | Price at or below lower band, volume spike |
> | Golden Cross | SMA50 crosses above SMA200 |
> | Earnings Rebound | Post-earnings dip within 10 sessions of beat |
> | Institutional Flow | Volume z-score > 2 with positive price action |
>
> Composite scores map to badges: **Strong Buy / Buy / Neutral / Sell / Strong Sell**
>
> ---
>
> ## Machine Learning (Walk-Forward)
>
> The ML layer uses **expanding-window walk-forward cross-validation** — the standard in quant finance. Each month, the model retrains on all available history and predicts the following month. This prevents lookahead bias far better than a single 70/30 split.
>
> **Target variables (not just binary direction):**
> - `fwd_return_21d` — raw 21-day forward return
> - - `fwd_sharpe_21d` — return / realized volatility (risk-adjusted)
>   - - `fwd_quintile_21d` — cross-sectional quintile rank (1=bottom, 5=top of universe)
>    
>     - **Models:**
>     - - LightGBM — primary model, fast gradient boosting on tabular data
>       - - Ridge regression — for return magnitude prediction
>         - - Ensemble — average of regime classifier + signal confidence + momentum score
>          
>           - **Feature engineering:**
>           - - Rolling z-scores of all indicators (e.g., RSI z-score over 252 days)
>             - - Cross-sectional ranks of each feature vs universe on each date
>               - - Lagged features (prior day RSI, 5-day RSI change, lagged momentum)
>                 - - Interaction features (low RSI + high volume + macro risk-on)
>                  
>                   - ---
>
> ## Backtesting
>
> All backtests run against 5 years of data and assume:
> - **Transaction cost:** 0.05% per trade (round-trip 0.10%)
> - - **Slippage:** fills at next-day open (not signal close)
>   - - **Position sizing:** fixed fractional (2% of portfolio per trade)
>     - - **Benchmark:** always report Sharpe vs SPY buy-and-hold
>      
>       - Results are stored in `backtest_results` with per-year rolling metrics and market-regime breakdowns.
>      
>       - ---
>
> ## Deployment
>
> Two branches run separate Streamlit Cloud apps:
>
> | Branch | Purpose | Dashboard |
> |---|---|---|
> | `master` | Personal | Portfolio + Analyze |
> | `public` | Public visitors | Analyze only |
>
> ---
>
> ## Setup (Local)
>
> ```bash
> git clone https://github.com/lUIZhMACEDO/quant-research-system.git
> cd quant-research-system
> pip install -r requirements.txt
>
> # Run the ingest pipeline (populates quant.db)
> python ingest.py
>
> # Run the dashboard
> streamlit run app.py
>
> # Run the daily report / email manually
> python main.py
> ```
>
> ---
>
> ## Environment Variables
>
> | Variable | Description | Required |
> |---|---|---|
> | `FINNHUB_API_KEY` | Finnhub real-time quotes and news | Yes |
> | `ANTHROPIC_API_KEY` | Claude API for strategy note generation | Yes |
> | `SENDER_EMAIL` | Gmail address for outbound reports | Yes |
> | `EMAIL_PASSWORD` | Gmail app password | Yes |
> | `RECIPIENT_EMAIL` | Report delivery address | Yes |
> | `TIINGO_API_KEY` | Tiingo EOD data (optional upgrade from yfinance) | No |
> | `DB_PATH` | Path to SQLite database (default: `quant.db`) | No |
> | `PUBLIC_MODE` | Set `0` to show Portfolio tab (default: `1`) | No |
>
> ---
>
> ## GitHub Actions (Daily Pipeline)
>
> `.github/workflows/daily-report.yml` runs `python main.py` Mon–Fri at 8:30 AM Eastern (12:30 UTC summer / 13:30 UTC winter).
>
> Required secrets: `FINNHUB_API_KEY`, `ANTHROPIC_API_KEY`, `SENDER_EMAIL`, `RECIPIENT_EMAIL`, `EMAIL_PASSWORD`
>
> For the ingest pipeline, add a second workflow triggered at 4:05 PM ET running `python ingest.py`.
>
> ---
>
> ## Upgrade Path
>
> | Upgrade | Impact |
> |---|---|
> | Swap yfinance → Tiingo (~$10/mo) | Institutional-quality adjusted EOD, cleaner splits |
> | Add Polygon.io free tier | Tick-level data, options flow, real-time quotes |
> | Add SEC EDGAR scraper | Actual 10-K/10-Q filing data for fundamentals |
> | SEC Form 4 (OpenInsider) | Insider buying/selling signals |
> | Options data: put/call ratio, GEX, max pain | Options-derived directional signals |
> | Quandl/Nasdaq Data Link | Alternative data, futures, commodities |
>
> ---
>
> ## Portfolio Persistence
>
> On Streamlit Cloud, `portfolio_save.json` does not persist across restarts. Your personal app loads from `MY_PORTFOLIO` in `main.py`. Edit that dict and push to `master` to persist changes.
