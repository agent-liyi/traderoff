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


# ---------------------------------------------------------------------------
# set_password + random "email-temp" placeholder hardening
# ---------------------------------------------------------------------------


def test_create_user_with_email_temp_uses_unguessable_password(email_db, monkeypatch):
    # The email-code login path calls _create_user with the legacy
    # placeholder "email-temp" so the account is auto-created. Verify the
    # stored password_hash is for a random secret, not for "email-temp"
    # (otherwise an attacker who knew the placeholder could password-login).
    seen = set()
    for i in range(5):
        user = auth._create_user(f"u{i}@example.com", "email-temp")
        with auth._DB_LOCK:
            row = auth._get_db().execute(
                "SELECT password_hash FROM users WHERE id = ?", (user.id,)
            ).fetchone()
        h = row["password_hash"]
        assert auth.verify_password("email-temp", h) is False
        assert auth.verify_password("wrong", h) is False
        seen.add(h)
    # every random hash is unique
    assert len(seen) == 5


def test_create_user_with_real_password_is_hashed_as_is(email_db):
    user = auth._create_user("user@example.com", "strongsecret")
    with auth._DB_LOCK:
        h = auth._get_db().execute(
            "SELECT password_hash FROM users WHERE id = ?", (user.id,)
        ).fetchone()["password_hash"]
    assert auth.verify_password("strongsecret", h) is True


def test_set_password_too_short_rejects(email_db):
    user = auth._create_user("user@example.com", "strongsecret")
    with pytest.raises(auth.AuthError):
        auth.set_password(user.id, "short")
    with pytest.raises(auth.AuthError):
        auth.set_password(user.id, "1234567")  # 7 chars


def test_set_password_overwrites_and_clears_login_attempts(email_db):
    from web.app import auth as a
    user = auth._create_user("user@example.com", "old-password")
    # simulate a prior failed-attempt lockout
    with auth._DB_LOCK:
        a._get_db().execute(
            "INSERT INTO login_attempts (email, failures, locked_until) VALUES (?, ?, ?)",
            ("user@example.com", 5, int(time.time() * 1000) + 60_000),
        )
    # without set_password the lockout would block login; set_password clears it
    auth.set_password(user.id, "newpassword")
    assert auth.login_password("user@example.com", "newpassword") is not None
    assert auth.login_password("user@example.com", "old-password") is None


# ---------------------------------------------------------------------------
# HTTP /api/auth/password/set endpoint
# ---------------------------------------------------------------------------


def _http_client(monkeypatch):
    """FastAPI TestClient with USERS_DB pointing at a temp file."""
    from fastapi.testclient import TestClient
    from web.app.main import app
    return TestClient(app)


def test_password_set_unauthenticated_returns_401(email_db, monkeypatch):
    client = _http_client(monkeypatch)
    r = client.post("/api/auth/password/set", json={"new_password": "newsecret"})
    assert r.status_code == 401


def test_password_set_too_short_returns_400(email_db, monkeypatch):
    client = _http_client(monkeypatch)
    monkeypatch.setattr(auth, "_email_provider_send", lambda email, code: code)
    monkeypatch.setattr(config, "SES_DEV_REVEAL", True)
    # log in via email-code path (uses _create_user with placeholder)
    r = client.post("/api/auth/email/send", json={"email": "u@example.com"})
    code = r.json()["code"]
    r2 = client.post("/api/auth/login", json={"email": "u@example.com", "code": code})
    assert r2.status_code == 200
    r3 = client.post("/api/auth/password/set", json={"new_password": "short"})
    assert r3.status_code == 400
    assert "8" in r3.json()["error"]


def test_password_set_authenticated_succeeds_and_enables_password_login(email_db, monkeypatch):
    client = _http_client(monkeypatch)
    monkeypatch.setattr(auth, "_email_provider_send", lambda email, code: code)
    monkeypatch.setattr(config, "SES_DEV_REVEAL", True)
    # register via email-code
    r = client.post("/api/auth/email/send", json={"email": "u@example.com"})
    code = r.json()["code"]
    r2 = client.post("/api/auth/login", json={"email": "u@example.com", "code": code})
    assert r2.status_code == 200
    # set password (cookie auto-managed by TestClient across requests)
    r3 = client.post("/api/auth/password/set", json={"new_password": "newsecret"})
    assert r3.status_code == 200
    # now password login works (the placeholder is no longer in effect)
    # log out first, then log back in via password
    client.post("/api/logout")
    r4 = client.post("/api/auth/login", json={"email": "u@example.com", "password": "newsecret"})
    assert r4.status_code == 200
    # and the wrong password still fails
    client.post("/api/logout")
    r5 = client.post("/api/auth/login", json={"email": "u@example.com", "password": "wrongpass"})
    assert r5.status_code == 401
