"""TDD tests for email-verification + password auth (replacing SMS/phone).

Red-phase: these email auth functions do not exist yet, so tests fail first.
"""

import time

import pytest

from web.app import auth, config


@pytest.fixture
def email_db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "USERS_DB", str(tmp_path / "users.email.sqlite"))
    monkeypatch.setattr(auth, "_db", None)
    yield auth._get_db()
    auth._db.close()
    monkeypatch.setattr(auth, "_db", None)


def test_hash_password_and_verify_roundtrip():
    h = auth.hash_password("secret123")
    assert auth.verify_password("secret123", h) is True
    assert auth.verify_password("wrong", h) is False


def test_send_email_code_returns_six_digit(email_db, monkeypatch):
    monkeypatch.setattr(auth, "_email_provider_send", lambda email, code: code)
    code = auth.send_email_code("user@example.com")
    assert len(code) == 6 and code.isdigit()


def test_verify_email_code_single_use(email_db, monkeypatch):
    monkeypatch.setattr(auth, "_email_provider_send", lambda email, code: code)
    code = auth.send_email_code("user@example.com")
    assert auth.verify_email_code("user@example.com", code) is True
    assert auth.verify_email_code("user@example.com", code) is False


def test_verify_email_code_expired(email_db, monkeypatch):
    monkeypatch.setattr(auth, "_email_provider_send", lambda email, code: code)
    code = auth.send_email_code("user@example.com")
    future_ms = int(time.time() * 1000) + auth.EMAIL_CODE_TTL_S * 1000 + 1000
    monkeypatch.setattr(time, "time", lambda: future_ms)
    assert auth.verify_email_code("user@example.com", code) is False


def test_email_send_rate_limited(email_db, monkeypatch):
    monkeypatch.setattr(auth, "_email_provider_send", lambda email, code: code)
    auth.send_email_code("user@example.com")
    with pytest.raises(auth.RateLimitError):
        auth.send_email_code("user@example.com")


def test_register_requires_valid_code(email_db, monkeypatch):
    monkeypatch.setattr(auth, "_email_provider_send", lambda email, code: code)
    auth.send_email_code("user@example.com")
    with pytest.raises(auth.AuthError):
        auth.register("user@example.com", "000000", "secret123")


def test_register_success_creates_user(email_db, monkeypatch):
    monkeypatch.setattr(auth, "_email_provider_send", lambda email, code: code)
    code = auth.send_email_code("user@example.com")
    user = auth.register("user@example.com", code, "secret123")
    assert user.id > 0
    assert user.name  # name derived from email local part


def test_register_rejects_duplicate_email(email_db, monkeypatch):
    monkeypatch.setattr(auth, "_email_provider_send", lambda email, code: code)
    code = auth.send_email_code("user@example.com")
    auth.register("user@example.com", code, "secret123")
    code2 = auth.send_email_code("user@example.com")
    with pytest.raises(auth.AuthError):
        auth.register("user@example.com", code2, "secret123")


def test_login_password_success(email_db):
    auth._create_user("user@example.com", "secret123")
    assert auth.login_password("user@example.com", "secret123") is not None


def test_login_password_wrong_then_locked(email_db):
    auth._create_user("user@example.com", "secret123")
    for _ in range(5):
        assert auth.login_password("user@example.com", "wrong") is None
    assert auth.login_password("user@example.com", "secret123") is None


def test_email_provider_fallback_when_unconfigured(email_db):
    # no SES credentials -> returns code (dev fallback)
    code = auth.send_email_code("user@example.com")
    assert len(code) == 6 and code.isdigit()
