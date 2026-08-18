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
    user = auth.find_or_create_wechat_user({"openid": "o1", "nickname": "测试", "headimgurl": ""})
    token = auth.create_session(user.id)
    got = auth.current_user(f"session={token}")
    assert got is not None
    assert got.id == user.id
    assert got.name == "测试"
    assert got.avatar_url == ""


def test_current_user_none_without_session(auth_db):
    assert auth.current_user(None) is None
    assert auth.current_user("") is None
    assert auth.current_user("other=1") is None


def test_current_user_unknown_token_returns_none(auth_db):
    user = auth.find_or_create_wechat_user({"openid": "o2", "nickname": "无名"})
    auth.create_session(user.id)
    assert auth.current_user("session=does-not-exist") is None


def test_current_user_with_expired_session_returns_none(auth_db, monkeypatch):
    user = auth.find_or_create_wechat_user({"openid": "o3", "nickname": "旧"})
    token = auth.create_session(user.id)
    token_hash = auth._sha256_hash(token)
    # Move "now" far into the future so the session is considered expired.
    future_ms = int(time.time() * 1000) + auth.SESSION_TTL_S * 1000 + 100000
    monkeypatch.setattr(time, "time", lambda: future_ms)
    assert auth.current_user(f"session={token}") is None
    row = auth._get_db().execute("SELECT 1 FROM sessions WHERE token_hash=?", (token_hash,)).fetchone()
    assert row is not None


def test_destroy_session_removes_it(auth_db):
    user = auth.find_or_create_wechat_user({"openid": "o4", "nickname": "删"})
    token = auth.create_session(user.id)
    assert auth.current_user(f"session={token}") is not None
    auth.destroy_session(f"session={token}")
    assert auth.current_user(f"session={token}") is None


def test_destroy_session_missing_cookie_is_noop(auth_db):
    auth.destroy_session(None)
    auth.destroy_session("")  # must not raise


# ---------------------------------------------------------------------------
# WeChat OAuth state
# ---------------------------------------------------------------------------


def test_create_and_consume_state_roundtrip(auth_db):
    state = auth.create_wechat_state()
    assert state
    assert auth.consume_wechat_state(state) is True
    assert auth.consume_wechat_state(state) is False  # single-use


def test_consume_wechat_state_rejects_missing(auth_db):
    assert auth.consume_wechat_state(None) is False
    assert auth.consume_wechat_state("") is False


def test_consume_wechat_state_unknown(auth_db):
    assert auth.consume_wechat_state("nope") is False


def test_consume_wechat_state_expired(auth_db, monkeypatch):
    state = auth.create_wechat_state()
    future_ms = int(time.time() * 1000) + auth.WECHAT_STATE_TTL_S * 1000 + 100000
    monkeypatch.setattr(time, "time", lambda: future_ms)
    assert auth.consume_wechat_state(state) is False


def test_build_wechat_authorize_url_structure(monkeypatch):
    monkeypatch.setattr(config, "WECHAT_APP_ID", "appid-1")
    url = auth.build_wechat_authorize_url("st")
    assert url.startswith("https://open.weixin.qq.com/connect/qrconnect")
    assert "appid=appid-1" in url
    assert "scope=snsapi_login" in url
    assert "state=st" in url
    assert "#wechat_redirect" in url


# ---------------------------------------------------------------------------
# find_or_create_wechat_user
# ---------------------------------------------------------------------------


def test_find_or_create_inserts_new_user(auth_db):
    u = auth.find_or_create_wechat_user({"openid": "new-openid", "nickname": "新用户", "headimgurl": "http://a/x.png"})
    assert u.id > 0
    assert u.name == "新用户"
    assert u.avatar_url == "http://a/x.png"


def test_find_or_create_returns_existing_and_updates_profile(auth_db):
    first = auth.find_or_create_wechat_user({"openid": "same", "nickname": "旧名", "headimgurl": "http://a/old.png"})
    second = auth.find_or_create_wechat_user({"openid": "same", "nickname": "新名", "headimgurl": "http://a/new.png"})
    assert second.id == first.id
    assert second.name == "新名"
    assert second.avatar_url == "http://a/new.png"
    row = auth._get_db().execute("SELECT name, avatar_url FROM users WHERE id=?", (first.id,)).fetchone()
    assert row["name"] == "新名"
    assert row["avatar_url"] == "http://a/new.png"


def test_find_or_create_nickname_none_defaults(auth_db):
    u = auth.find_or_create_wechat_user({"openid": "nonick"})
    assert u.name == "微信用户"
    assert u.avatar_url is None


def test_find_or_create_truncates_long_nickname(auth_db):
    long_name = "尼" * 80
    u = auth.find_or_create_wechat_user({"openid": "long", "nickname": long_name})
    assert len(u.name) <= 40


def test_wechat_openid_unique_reuses_existing(auth_db):
    auth.find_or_create_wechat_user({"openid": "uniq"})
    auth.find_or_create_wechat_user({"openid": "uniq"})
    count = auth._get_db().execute("SELECT count(*) AS c FROM users WHERE wechat_openid='uniq'").fetchone()
    assert count["c"] == 1


# ---------------------------------------------------------------------------
# _fetch_wechat_json (network mocks)
# ---------------------------------------------------------------------------


def test_fetch_wechat_json_raises_on_non_200(monkeypatch):
    class FakeResp:
        status_code = 500

    monkeypatch.setattr("httpx.get", lambda url, **kw: FakeResp())
    with pytest.raises(RuntimeError, match="微信接口请求失败"):
        auth._fetch_wechat_json("http://x")


def test_fetch_wechat_json_raises_on_errcode(monkeypatch):
    class FakeResp:
        status_code = 200

        def json(self):
            return {"errcode": 40013, "errmsg": "invalid appid"}

    monkeypatch.setattr("httpx.get", lambda url, **kw: FakeResp())
    with pytest.raises(RuntimeError, match="40013"):
        auth._fetch_wechat_json("http://x")


def test_fetch_wechat_json_returns_json_on_success(monkeypatch):
    class FakeResp:
        status_code = 200

        def json(self):
            return {"openid": "ok"}

    monkeypatch.setattr("httpx.get", lambda url, **kw: FakeResp())
    assert auth._fetch_wechat_json("http://x") == {"openid": "ok"}
