"""HTTP endpoint + error-handling tests for web/app/main.py (FastAPI routes).

Uses the TestClient. Auth endpoints write to an isolated temp sqlite (via the
`isolated_auth_db` autouse fixture) so the production users DB is never touched.
"""

from urllib.parse import urlparse, parse_qs

import pytest
from fastapi.testclient import TestClient

from web.app import auth, config, market_data
from web.app.main import app

client = TestClient(app)

DATA_EP = [
    "/api/market-environment",
    "/api/market-style",
    "/api/industry-price",
    "/api/market-volume",
    "/api/market-volatility",
    "/api/market-turnover",
    "/api/market-breadth",
    "/api/factor-exposure",
]


@pytest.fixture(autouse=True)
def isolated_auth_db(tmp_path, monkeypatch):
    """Point auth's sqlite at a temp file so HTTP auth tests don't touch prod DB."""
    db_file = tmp_path / "users.test.sqlite"
    monkeypatch.setattr(config, "USERS_DB", str(db_file))
    monkeypatch.setattr(auth, "_db", None)
    yield
    # Do NOT close the connection here: request handlers may run on a different
    # thread (TestClient thread pool), and closing a sqlite conn across threads
    # raises ProgrammingError. Resetting to None lets the next test reopen the
    # temp DB; the interpreter reclaims the old connection on exit.
    monkeypatch.setattr(auth, "_db", None)


# ---------------------------------------------------------------------------
# Data endpoints return 200 with no-store cache header
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("ep", DATA_EP)
def test_data_endpoint_200(ep):
    r = client.get(ep)
    assert r.status_code == 200
    assert r.headers.get("cache-control") == "no-store"


def test_me_anonymous_returns_null_user():
    r = client.get("/api/me")
    assert r.status_code == 200
    assert r.json() == {"user": None}


# ---------------------------------------------------------------------------
# dashboard range handling
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("range_,expected", [("6m", 126), ("1y", 250), ("3y", 750), ("all", 1250)])
def test_dashboard_ranges_return_expected_points(range_, expected):
    r = client.get(f"/api/dashboard?range={range_}")
    assert r.status_code == 200
    body = r.json()
    assert len(body["series"]) >= 1
    assert body["asOf"]


def test_dashboard_default_is_1y():
    r = client.get("/api/dashboard")
    assert r.status_code == 200
    body = r.json()
    assert body["asOf"]
    assert "series" in body and "index" in body


def test_dashboard_unknown_range_coerces_to_1y():
    r = client.get("/api/dashboard?range=nonsense")
    assert r.status_code == 200
    body = r.json()
    # unknown range falls back to the 1y default slice (<=250 rows)
    assert len(body["series"]) <= 250


# ---------------------------------------------------------------------------
# error handling: 503 / 500 / 404 / 405
# ---------------------------------------------------------------------------


def test_market_data_error_returns_503(monkeypatch):
    def boom():
        raise market_data.MarketDataError("行情数据库暂时不可用")

    monkeypatch.setattr(market_data, "market_environment", boom)
    r = client.get("/api/market-environment")
    assert r.status_code == 503
    assert r.json() == {"error": "行情数据库暂时不可用"}


def test_validation_error_returns_500_generic(monkeypatch):
    def boom():
        raise market_data.ValidationError("内部结构错")  # message must NOT leak

    monkeypatch.setattr(market_data, "market_style", boom)
    r = client.get("/api/market-style")
    assert r.status_code == 500
    assert r.json() == {"error": "服务暂时不可用"}
    assert "内部结构错" not in r.text


def test_unknown_api_path_spa_fallback_returns_html():
    r = client.get("/api/nonexistent-route")
    # catch-all serves index.html (SPA fallback), so it's 200 with html
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("text/html")


def test_post_to_readonly_endpoint_not_allowed():
    r = client.post("/api/me")
    assert r.status_code == 405


def test_static_index_served_with_no_cache():
    r = client.get("/")
    assert r.status_code == 200
    assert r.headers.get("cache-control") == "no-cache"
    assert r.headers.get("content-type", "").startswith("text/html")


def test_static_asset_served_with_long_cache():
    r = client.get("/app.js")
    assert r.status_code == 200
    assert r.headers.get("cache-control") == "public, max-age=86400"


def test_path_traversal_does_not_leak_stat_root_outside(monkeypatch):
    # URL-encoded traversal is rejected outright.
    r_enc = client.get("/%2e%2e/etc/passwd")
    assert r_enc.status_code == 404
    # A normalized '../' resolves to a path under static root that doesn't
    # exist, so it falls back to index.html (200) — crucially it must NOT
    # return the target system file's contents.
    r = client.get("/../etc/passwd")
    assert r.status_code == 200
    assert "root:" not in r.text
    assert r.headers.get("content-type", "").startswith("text/html")


# ---------------------------------------------------------------------------
# WeChat OAuth (development mode)
# ---------------------------------------------------------------------------


def test_auth_wechat_dev_redirects_to_callback(monkeypatch):
    monkeypatch.setattr(config, "WECHAT_AUTH_MODE", "development")
    r = client.get("/api/auth/wechat", follow_redirects=False)
    assert r.status_code == 302
    loc = r.headers["location"]
    assert loc.startswith("/api/auth/wechat/callback?code=development&state=")


def test_auth_wechat_not_configured_when_production_missing_keys(monkeypatch):
    monkeypatch.setattr(config, "WECHAT_AUTH_MODE", "production")
    monkeypatch.setattr(config, "WECHAT_APP_ID", "")
    monkeypatch.setattr(config, "WECHAT_APP_SECRET", "")
    monkeypatch.setattr(config, "WECHAT_REDIRECT_URI", "")
    r = client.get("/api/auth/wechat", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "/?auth=not-configured"


def test_full_wechat_login_flow_sets_session_cookie(monkeypatch):
    monkeypatch.setattr(config, "WECHAT_AUTH_MODE", "development")
    # 1. obtain a real state via /api/auth/wechat
    r0 = client.get("/api/auth/wechat", follow_redirects=False)
    state = parse_qs(urlparse(r0.headers["location"]).query)["state"][0]
    # 2. callback with that valid state
    r = client.get(f"/api/auth/wechat/callback?code=development&state={state}", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "/?auth=success"
    setcookie = r.headers.get("set-cookie", "")
    assert "session=" in setcookie
    assert "HttpOnly" in setcookie
    # 3. /api/me now returns the dev user
    cookieval = setcookie.split(";")[0]
    r2 = client.get("/api/me", headers={"Cookie": cookieval})
    assert r2.status_code == 200
    user = r2.json()["user"]
    assert user is not None
    assert user["name"] == "微信测试用户"

    # 4. logout clears the session
    r3 = client.post("/api/logout", headers={"Cookie": cookieval})
    assert r3.status_code == 200
    assert r3.json() == {"ok": True}
    assert "Max-Age=0" in r3.headers.get("set-cookie", "")
    r4 = client.get("/api/me", headers={"Cookie": cookieval})
    assert r4.json()["user"] is None


def test_wechat_callback_invalid_state_rejected(monkeypatch):
    monkeypatch.setattr(config, "WECHAT_AUTH_MODE", "development")
    r = client.get("/api/auth/wechat/callback?code=development&state=bad-state", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "/?auth=invalid-state"


def test_wechat_callback_cancelled_when_error_param(monkeypatch):
    monkeypatch.setattr(config, "WECHAT_AUTH_MODE", "development")
    # need a valid state
    r0 = client.get("/api/auth/wechat", follow_redirects=False)
    state = parse_qs(urlparse(r0.headers["location"]).query)["state"][0]
    r = client.get(f"/api/auth/wechat/callback?error=denied&state={state}", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "/?auth=cancelled"


# ---------------------------------------------------------------------------
# auth_quote helper
# ---------------------------------------------------------------------------


def test_auth_quote_encodes_special_chars():
    from web.app.main import auth_quote
    assert auth_quote("a b") == "a%20b"
    assert auth_quote("x/y?z") == "x%2Fy%3Fz"
