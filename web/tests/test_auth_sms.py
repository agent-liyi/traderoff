"""TDD tests for SMS-verification + password auth (replacing WeChat OAuth).

Red-phase tests: these functions do not exist yet, so they fail first.
"""

import time

import pytest

from web.app import auth, config


@pytest.fixture
def sms_db(tmp_path, monkeypatch):
    """Isolate auth sqlite and reset rate-limit state."""
    monkeypatch.setattr(config, "USERS_DB", str(tmp_path / "users.sms.sqlite"))
    monkeypatch.setattr(auth, "_db", None)
    # clear any in-memory rate-limit state (defined on the module after impl)
    for attr in ("_sms_send_last", "_sms_send_daily", "_login_fail"):
        if hasattr(auth, attr):
            monkeypatch.setattr(auth, attr, None)
    yield auth._get_db()
    auth._db.close()
    monkeypatch.setattr(auth, "_db", None)


# ---------------------------------------------------------------------------
# password hashing
# ---------------------------------------------------------------------------


def test_hash_password_produces_different_salts():
    h1 = auth.hash_password("secret123")
    h2 = auth.hash_password("secret123")
    assert h1 != h2  # salted


def test_verify_password_roundtrip():
    h = auth.hash_password("secret123")
    assert auth.verify_password("secret123", h) is True
    assert auth.verify_password("wrong", h) is False


# ---------------------------------------------------------------------------
# SMS code send + verify
# ---------------------------------------------------------------------------


def test_send_sms_code_returns_six_digit(sms_db, monkeypatch):
    monkeypatch.setattr(auth, "_sms_provider_send", lambda phone, code: code)
    code = auth.send_sms_code("13800138000")
    assert len(code) == 6
    assert code.isdigit()


def test_verify_sms_code_single_use(sms_db, monkeypatch):
    monkeypatch.setattr(auth, "_sms_provider_send", lambda phone, code: code)
    code = auth.send_sms_code("13800138000")
    assert auth.verify_sms_code("13800138000", code) is True
    assert auth.verify_sms_code("13800138000", code) is False  # consumed


def test_verify_sms_code_expired(sms_db, monkeypatch):
    monkeypatch.setattr(auth, "_sms_provider_send", lambda phone, code: code)
    code = auth.send_sms_code("13800138000")
    future_ms = int(time.time() * 1000) + auth.SMS_CODE_TTL_S * 1000 + 1000
    monkeypatch.setattr(time, "time", lambda: future_ms)
    assert auth.verify_sms_code("13800138000", code) is False


def test_verify_sms_code_wrong(sms_db, monkeypatch):
    monkeypatch.setattr(auth, "_sms_provider_send", lambda phone, code: code)
    auth.send_sms_code("13800138000")
    assert auth.verify_sms_code("13800138000", "000000") is False


def test_sms_send_rate_limited_60s(sms_db, monkeypatch):
    monkeypatch.setattr(auth, "_sms_provider_send", lambda phone, code: code)
    auth.send_sms_code("13800138000")
    with pytest.raises(auth.RateLimitError):
        auth.send_sms_code("13800138000")  # within 60s window


def test_sms_send_daily_cap(sms_db, monkeypatch):
    monkeypatch.setattr(auth, "_sms_provider_send", lambda phone, code: code)
    # exhaust the daily quota by simulating sends (each new day resets count)
    for _ in range(auth.SMS_CODE_MAX_DAILY):
        t = time.time() + (1000 + _ * 1000)  # move past the send-window each time
        monkeypatch.setattr(time, "time", lambda now=t: now)
        auth.send_sms_code("13900139000")
    with pytest.raises(auth.RateLimitError):
        auth.send_sms_code("13900139000")


# ---------------------------------------------------------------------------
# register / login (password)
# ---------------------------------------------------------------------------


def test_register_requires_valid_sms_code(sms_db, monkeypatch):
    monkeypatch.setattr(auth, "_sms_provider_send", lambda phone, code: code)
    auth.send_sms_code("13800138000")
    with pytest.raises(auth.AuthError):
        auth.register("13800138000", "000000", "secret123")  # wrong code


def test_register_success_creates_user(sms_db, monkeypatch):
    monkeypatch.setattr(auth, "_sms_provider_send", lambda phone, code: code)
    code = auth.send_sms_code("13800138000")
    user = auth.register("13800138000", code, "secret123")
    assert user.id > 0
    assert user.phone == "13800138000"


def test_login_password_success(sms_db):
    auth._create_user("13800138000", "secret123")
    tok = auth.login_password("13800138000", "secret123")
    assert tok is not None


def test_login_password_wrong_then_locked(sms_db):
    auth._create_user("13800138000", "secret123")
    for _ in range(5):
        assert auth.login_password("13800138000", "wrong") is None
    # after 5 failures the account is locked
    assert auth.login_password("13800138000", "secret123") is None


# ---------------------------------------------------------------------------
# weak password
# ---------------------------------------------------------------------------


def test_hash_password_rejects_none():
    with pytest.raises(TypeError):
        auth.hash_password(None)
