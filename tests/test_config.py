from pathlib import Path

from quant_research.config import load_settings


def test_defaults_when_env_is_empty():
    s = load_settings({})
    assert s.public_mode is True
    assert s.smtp_host == "smtp.gmail.com"
    assert s.smtp_port == 587
    assert s.db_path == "quant.db"
    assert s.app_password is None
    assert s.email_configured is False


def test_reads_secrets_and_strips_whitespace():
    s = load_settings(
        {
            "SENDER_EMAIL": " bot@example.com ",
            "EMAIL_PASSWORD": "app-pass",
            "APP_PASSWORD": "dashboard-pass",
            "FINNHUB_API_KEY": "",
        }
    )
    assert s.sender_email == "bot@example.com"
    assert s.email_configured is True
    assert s.app_password == "dashboard-pass"
    assert s.finnhub_api_key is None  # blank counts as unset


def test_bool_and_number_parsing():
    assert load_settings({"PUBLIC_MODE": "0"}).public_mode is False
    assert load_settings({"PUBLIC_MODE": "yes"}).public_mode is True
    assert load_settings({"SMTP_PORT": "465"}).smtp_port == 465
    assert load_settings({"SMTP_PORT": "not-a-port"}).smtp_port == 587
    assert load_settings({"ACCOUNT_SIZE": "25000"}).account_size == 25000.0


def test_state_paths_follow_state_dir(tmp_path: Path):
    s = load_settings({"STATE_DIR": str(tmp_path)})
    assert s.scores_cache_file == tmp_path / "scores_cache.json"
    assert s.alerts_file == tmp_path / "alerts.json"
