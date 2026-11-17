"""Headless Streamlit run of the real ``app.py``: the password gate, and the public landing page behind it."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for key in ("APP_PASSWORD", "PUBLIC_MODE", "SENDER_EMAIL", "EMAIL_PASSWORD"):
        monkeypatch.delenv(key, raising=False)
    from quant_research.config import reset_settings

    reset_settings()
    yield
    reset_settings()


def test_dashboard_refuses_to_run_without_app_password():
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    assert any("APP_PASSWORD is not configured" in e.value for e in at.error)
    assert not at.text_input  # no password box: nothing to brute-force


def test_wrong_password_is_rejected(monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "correct-horse")
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.text_input(key="pwd_gate").input("wrong")
    at.button[0].click().run()
    assert [e.value for e in at.error] == ["Incorrect password."]
    assert "authenticated" not in at.session_state
    assert "Analyze Stocks" not in [b.label for b in at.button]  # nothing behind the gate rendered


def test_correct_password_shows_public_landing_page(monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "correct-horse")
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.text_input(key="pwd_gate").input("correct-horse")
    at.button[0].click().run()
    assert not at.exception
    assert at.session_state["authenticated"] is True
    assert at.session_state["page_mode"] == "custom"  # PUBLIC_MODE defaults on
    labels = [b.label for b in at.button]
    assert "Analyze Stocks" in labels and "My Portfolio" not in labels
