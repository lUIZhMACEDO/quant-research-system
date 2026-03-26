# Stock Analyst

> Version 3.1.0
>
> A full-featured automated stock analysis platform with a live Streamlit dashboard, personal portfolio tracker, composite signal scoring, technical indicators, AI strategy notes, and a daily email report delivered via GitHub Actions.
>
> ---
>
> ## Features
>
> ### Dashboard (app.py)
> - **Live Ticker Tape** — real-time price scroll for your watchlist
> - - **Market KPIs** — SPY, QQQ, VIX, and sector ETF performance at a glance
>   - - **Analyze Any Stock** — enter any ticker to get a full breakdown: technicals, fundamentals, analyst ratings, earnings calendar, relative strength, and an AI-generated strategy note
>     - - **My Portfolio** — personal holdings tracker with P&L, position sizing, risk dashboard, and strategy timeline (hidden on the public deployment)
>       - - **Send Email Report** — send a full personalized HTML report to any email address directly from the dashboard
>         - - **Interactive Charts** — OHLCV candlestick + volume charts, sector allocation donut, P&L bar chart (powered by Plotly)
>           - - **Animated Loading Screen** — smooth UX with a starfield background
>            
>             - ### Daily Report Engine (main.py)
>             - - **Pre-market Movers** — top gainers/losers before market open
>               - - **S&P 500 Movers** — daily top gainers and losers across the full index
>                 - - **Macro News** — aggregated headlines with market impact scoring
>                   - - **Weekly Catalysts** — upcoming earnings, economic events, and Fed dates
>                     - - **Portfolio Analysis** — full report on your personal holdings including signals, scores, and risk metrics
>                       - - **Momentum & Swing Picks** — curated stock picks with multi-strategy signal scoring
>                         - - **Technical Snapshot** — RSI, MACD, Bollinger Bands, Golden Cross, ATR for every pick
>                           - - **Risk Dashboard** — position-level and portfolio-level risk metrics
>                             - - **Strategy Timeline** — visual breakdown of active strategies per holding
>                               - - **Friday Recap** — weekly summary section on Fridays
>                                 - - **AI Strategy Notes** — Anthropic Claude generates a plain-language trade rationale per stock
>                                   - - **Automated Scheduling** — runs Mon–Fri at 8:30 AM Eastern via GitHub Actions and emails the full report
>                                    
>                                     - ### Trading Strategies
>                                     - The scoring engine evaluates each stock against five strategies simultaneously:
>                                     - - `RSI + MACD` — momentum confirmation
>                                       - - `Bollinger Band Mean Reversion` — oversold bounce setups
>                                         - - `Golden Cross` — 50/200 MA trend following
>                                           - - `Earnings Rebound` — post-earnings recovery plays
>                                             - - `Institutional Flow` — volume-weighted accumulation signals
>                                              
>                                               - Each strategy produces a signal score; scores are combined into a composite rating displayed as a badge (Strong Buy / Buy / Neutral / Sell).
>                                              
>                                               - ---
>
> ## Deployment
>
> The repo uses **two branches** to run two separate Streamlit Cloud apps from the same codebase:
>
> | Branch   | Purpose                        | Streamlit App               |
> |----------|--------------------------------|-----------------------------|
> | `master` | Personal version               | Shows My Portfolio + Analyze |
> | `public` | Public version for visitors    | Shows Analyze only           |
>
> ### Steps
>
> 1. Push both branches to GitHub:
> 2. ```bash
>    git push origin master
>    git push origin public
>    ```
>
> 2. On [share.streamlit.io](https://share.streamlit.io), create two apps:
>
> 3. **App 1 — Public**
> 4. - Branch: `public`
>    - - Main file: `app.py`
>      - - Secrets: `FINNHUB_API_KEY`, `ANTHROPIC_API_KEY`, `SENDER_EMAIL`, `EMAIL_PASSWORD`
>       
>        - **App 2 — Personal**
>        - - Branch: `master`
>          - - Main file: `app.py`
>            - - Secrets: same as above, plus `PUBLIC_MODE = 0`
>             
>              - Setting `PUBLIC_MODE = 0` unlocks the **My Portfolio** tab.
>             
>              - ---
>
> ## Setup (Local)
>
> ### 1. Clone the repo
>
> ```bash
> git clone https://github.com/lUIZhMACEDO/ai-stock-analyst.git
> cd ai-stock-analyst
> ```
>
> ### 2. Install dependencies
>
> ```bash
> pip install -r requirements.txt
> ```
>
> ### 3. Configure environment variables
>
> Create a `.env` file or set these as environment variables:
>
> | Variable            | Description                                         | Required |
> |---------------------|-----------------------------------------------------|----------|
> | `FINNHUB_API_KEY`   | Finnhub API key for real-time market data           | Yes      |
> | `ANTHROPIC_API_KEY` | Claude API key for AI strategy notes                | Yes      |
> | `SENDER_EMAIL`      | Gmail address to send reports from                  | Yes      |
> | `EMAIL_PASSWORD`    | Gmail app password                                  | Yes      |
> | `RECIPIENT_EMAIL`   | Email address to receive the daily report           | Yes      |
> | `PUBLIC_MODE`       | Set to `0` to show My Portfolio (default: `1`)      | No       |
>
> ### 4. Run the dashboard
>
> ```bash
> streamlit run app.py
> ```
>
> ### 5. Run the daily report manually
>
> ```bash
> python main.py
> ```
>
> ---
>
> ## GitHub Actions (Daily Email)
>
> A workflow at `.github/workflows/daily-report.yml` runs `python main.py` automatically Mon–Fri at 8:30 AM Eastern (12:30 UTC in summer, 13:30 UTC in winter).
>
> Set the following **repository secrets** under Settings → Secrets → Actions:
>
> - `FINNHUB_API_KEY`
> - - `ANTHROPIC_API_KEY`
>   - - `SENDER_EMAIL`
>     - - `RECIPIENT_EMAIL`
>       - - `EMAIL_PASSWORD`
>        
>         - ---
>
> ## Project Structure
>
> ```
> ai-stock-analyst/
> ├── app.py                          # Streamlit dashboard (UI)
> ├── main.py                         # Report engine + email sender + scheduler
> ├── requirements.txt                # Python dependencies
> ├── packages.txt                    # System packages for Streamlit Cloud
> ├── .streamlit/
> │   └── config.toml                 # Streamlit theme config
> ├── .github/
> │   └── workflows/
> │       └── daily-report.yml        # GitHub Actions scheduled job
> └── .devcontainer/
>     └── devcontainer.json           # Dev container config
> ```
>
> ---
>
> ## Dependencies
>
> - `streamlit` — dashboard UI framework
> - - `plotly` — interactive charts
>   - - `yfinance` — stock price and fundamentals data
>     - - `finnhub-python` — real-time quotes and news
>       - - `anthropic` — Claude AI for strategy notes
>         - - `ta` — technical analysis indicators (RSI, MACD, BB, etc.)
>           - - `pandas` / `numpy` — data processing
>             - - `feedparser` — RSS news feeds
>               - - `beautifulsoup4` — web scraping
>                 - - `requests` — HTTP client
>                   - - `pytz` — timezone handling
>                     - - `python-dotenv` — local environment variables
>                       - - `fastapi` / `uvicorn` / `httpx` — optional API layer
>                        
>                         - ---
>
> ## Portfolio Persistence
>
> On Streamlit Cloud, `portfolio_save.json` does **not** persist across restarts. Your personal app loads your portfolio from the `MY_PORTFOLIO` dict in `main.py`. Any edits made during a session are in memory only and will reset on the next restart.
>
> To persist changes, update `MY_PORTFOLIO` directly in `main.py` and push to `master`.
