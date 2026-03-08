# AI Stock Analyst

Two Streamlit deployments from the same repo — one public, one personal.

## Branches

| Branch   | Purpose                    | Streamlit app          |
|----------|----------------------------|-------------------------|
| **master** | Your personal version      | My Portfolio + Analyze Stocks |
| **public** | Public version for visitors | Analyze Stocks only     |

## Deploy Both on Streamlit Cloud

### 1. Push both branches to GitHub

```bash
git push origin master
git push origin public
```

### 2. Create two apps on [share.streamlit.io](https://share.streamlit.io)

**App 1 — Public (for visitors)**  
- Repo: your `ai-stock-analyst`  
- Branch: **public**  
- Main file: `app.py`  
- Secrets: `FINNHUB_API_KEY`, `ANTHROPIC_API_KEY`, `SENDER_EMAIL`, `EMAIL_PASSWORD` (optional)

**App 2 — Personal (for you)**  
- Repo: same `ai-stock-analyst`  
- Branch: **master**  
- Main file: `app.py`  
- Secrets: same as above, **plus** `PUBLIC_MODE` = `0` (to show My Portfolio)

### 3. Result

- **Public app** → visitors only see "Analyze Stocks"
- **Personal app** → you see "My Portfolio" with your holdings from `main.py`

## Note on portfolio persistence

On Streamlit Cloud, `portfolio_save.json` does not persist across restarts. Your personal app loads your portfolio from `MY_PORTFOLIO` in `main.py`. Edits during a session are in memory only.
