"""Unit tests for web/app/auth.py (sessions, cookies, WeChat OAuth helpers).

Each test gets its own temporary sqlite DB so sessions/states never leak
between tests and never touch the production users.sqlite.
"""

import time

import pytest

from web.app import auth, config


@pytest.fixture
def auth_db(tmp_path, monkeypatch):
    """Reset auth's module-level sqlite singleton and point it at a temp DB."""
    db_file = tmp_path / "users.test.sqlite"
    monkeypatch.setattr(config, "USERS_DB", str(db_file))
    monkeypatch.setattr(auth, "_db", None)
    # Recreate the singleton so it opens the fresh temp DB with the schema.
    db = auth._get_db()
    yield db
    auth._db.close()
    monkeypatch.setattr(auth, "_db", None)


# ---------------------------------------------------------------------------
# _sha256_hash / _cookie
# ---------------------------------------------------------------------------


def test_sha256_hash_stable():
    assert auth._sha256_hash("abc") == auth._sha256_hash("abc")
    assert auth._sha256_hash("abc") != auth._sha256_hash("abd")
    assert len(auth._sha256_hash("anything")) == 64


def test_cookie_parser_handles_multiple_pairs_and_whitespace():
    header = "a=1; b = 2 ;  c=three"
    parsed = auth._cookie(header)
    assert parsed == {"a": "1", "b": "2", "c": "three"}


def test_cookie_parser_empty_and_malformed():
    assert auth._cookie("") == {}
    assert auth._cookie("no-equals-here") == {}
    assert auth._cookie(";)") == {}


# ---------------------------------------------------------------------------
# session cookie format
# ---------------------------------------------------------------------------


def test_session_cookie_includes_attributes():
    cookie = auth.session_cookie("tok123")
    assert "session=tok123" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie
    assert "Path=/" in cookie
    assert f"Max-Age={auth.SESSION_TTL_S}" in cookie


def test_session_cookie_urlencodes_token():
    # quote() keeps '/' by default; space is encoded.
    cookie = auth.session_cookie("a b/c")
    assert "a%20b/c" in cookie


def test_clear_session_cookie_has_max_age_zero():
    c = auth.clear_session_cookie()
    assert c.startswith("session=")
    assert "Max-Age=0" in c
    assert "HttpOnly" in c


# ---------------------------------------------------------------------------
# public_user
# ---------------------------------------------------------------------------


def test_public_user_none():
    assert auth.public_user(None) is None


def test_public_user_maps_fields():
    u = auth.User(id=7, name="张三", avatar_url="http://x/a.png")
    assert auth.public_user(u) == {"id": 7, "name": "张三", "avatarUrl": "http://x/a.png"}


# ---------------------------------------------------------------------------
# sessions: create / current / destroy
# ---------------------------------------------------------------------------


def test_create_and_current_user_roundtrip(auth_db):
    user = auth._create_user("13800000001", "secret123")
    token = auth.create_session(user.id)
    got = auth.current_user(f"session={token}")
    assert got is not None
    assert got.id == user.id
    assert got.name == "0001"
    assert got.avatar_url is None


def test_current_user_none_without_session(auth_db):
    assert auth.current_user(None) is None
    assert auth.current_user("") is None
    assert auth.current_user("other=1") is None


def test_current_user_unknown_token_returns_none(auth_db):
    user = auth._create_user("13800000002", "secret123")
    auth.create_session(user.id)
    assert auth.current_user("session=does-not-exist") is None


def test_current_user_with_expired_session_returns_none(auth_db, monkeypatch):
    user = auth._create_user("13800000003", "secret123")
    token = auth.create_session(user.id)
    token_hash = auth._sha256_hash(token)
    # Move "now" far into the future so the session is considered expired.
    future_ms = int(time.time() * 1000) + auth.SESSION_TTL_S * 1000 + 100000
    monkeypatch.setattr(time, "time", lambda: future_ms)
    assert auth.current_user(f"session={token}") is None
    row = auth._get_db().execute("SELECT 1 FROM sessions WHERE token_hash=?", (token_hash,)).fetchone()
    assert row is not None


def test_destroy_session_removes_it(auth_db):
    user = auth._create_user("13800000004", "secret123")
    token = auth.create_session(user.id)
    assert auth.current_user(f"session={token}") is not None
    auth.destroy_session(f"session={token}")
    assert auth.current_user(f"session={token}") is None


def test_destroy_session_missing_cookie_is_noop(auth_db):
    auth.destroy_session(None)
    auth.destroy_session("")  # must not raise


