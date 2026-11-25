"""Runtime configuration.

Every secret and deployment setting comes from environment variables (or a local
``.env`` file during development). Nothing secret is hard-coded in the source tree.
See ``.env.example`` at the repo root for the full list.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"

_TRUE = {"1", "true", "yes", "on"}


def _as_bool(value: str | None, default: bool) -> bool:
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in _TRUE


def _as_int(value: str | None, default: int) -> int:
    try:
        return int(value) if value not in (None, "") else default
    except ValueError:
        return default


def _as_float(value: str | None, default: float) -> float:
    try:
        return float(value) if value not in (None, "") else default
    except ValueError:
        return default


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


@dataclass(frozen=True)
class Settings:
    """Immutable view of the environment, loaded once per process via :func:`get_settings`."""

    # Email report (SMTP)
    sender_email: str | None = None
    email_password: str | None = None
    recipient_email: str | None = None
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587

    # Data / API providers
    finnhub_api_key: str | None = None
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-haiku-4-5-20251001"
    tiingo_api_key: str | None = None

    # Dashboard
    app_password: str | None = None
    public_mode: bool = True

    # Storage and state
    db_path: str = "quant.db"
    portfolio_path: Path = DATA_DIR / "master_portfolio.json"
    state_dir: Path = REPO_ROOT

    # Research parameters
    account_size: float = 10_000.0
    finnhub_rate_limit_delay: float = 0.30

    # Optional webhook for alert pushes (disabled unless set)
    push_alert_url: str | None = None

    @property
    def email_configured(self) -> bool:
        return bool(self.sender_email and self.email_password)

    @property
    def scores_cache_file(self) -> Path:
        return self.state_dir / "scores_cache.json"

    @property
    def alerts_file(self) -> Path:
        return self.state_dir / "alerts.json"


def load_settings(env: Mapping[str, str] | None = None) -> Settings:
    """Build :class:`Settings` from ``env`` (defaults to ``os.environ``).

    When reading the real environment, a ``.env`` file is loaded first if
    ``python-dotenv`` is installed. Passing an explicit mapping (as the tests do)
    skips that step so results are deterministic.
    """
    if env is None:
        try:
            from dotenv import load_dotenv

            load_dotenv(REPO_ROOT / ".env")
        except ImportError:  # pragma: no cover - dotenv is in requirements
            pass
        env = os.environ

    get = env.get
    return Settings(
        sender_email=_clean(get("SENDER_EMAIL")),
        email_password=_clean(get("EMAIL_PASSWORD")),
        recipient_email=_clean(get("RECIPIENT_EMAIL")),
        smtp_host=_clean(get("SMTP_HOST")) or "smtp.gmail.com",
        smtp_port=_as_int(get("SMTP_PORT"), 587),
        finnhub_api_key=_clean(get("FINNHUB_API_KEY")),
        anthropic_api_key=_clean(get("ANTHROPIC_API_KEY")),
        anthropic_model=_clean(get("ANTHROPIC_MODEL")) or "claude-haiku-4-5-20251001",
        tiingo_api_key=_clean(get("TIINGO_API_KEY")),
        app_password=_clean(get("APP_PASSWORD")),
        public_mode=_as_bool(get("PUBLIC_MODE"), default=True),
        db_path=_clean(get("DB_PATH")) or "quant.db",
        portfolio_path=Path(_clean(get("PORTFOLIO_PATH")) or DATA_DIR / "master_portfolio.json"),
        state_dir=Path(_clean(get("STATE_DIR")) or REPO_ROOT),
        account_size=_as_float(get("ACCOUNT_SIZE"), 10_000.0),
        finnhub_rate_limit_delay=_as_float(get("FINNHUB_RATE_LIMIT_DELAY"), 0.30),
        push_alert_url=_clean(get("PUSH_ALERT_URL")),
    )


_settings: Settings | None = None


def get_settings() -> Settings:
    """Process-wide settings, loaded lazily on first use."""
    global _settings
    if _settings is None:
        _settings = load_settings()
    return _settings


def reset_settings() -> None:
    """Forget cached settings (used after the dashboard copies Streamlit secrets into the env)."""
    global _settings
    _settings = None
