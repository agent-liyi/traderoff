"""FastAPI app entrypoint, replicating the original Node server.js routing.

Routes (unchanged contracts):
  GET  /api/dashboard?range=6m|1y|3y|all      (default 1y)
  GET  /api/market-environment
  GET  /api/market-style
  GET  /api/industry-price
  GET  /api/market-volume
  GET  /api/market-volatility
  GET  /api/market-turnover
  GET  /api/market-breadth
  GET  /api/factor-exposure
  GET  /api/me
  GET  /api/auth/wechat
  GET  /api/auth/wechat/callback
  POST /api/logout
plus static file serving with SPA fallback to index.html.

Errors: 503 -> {"error": message}; otherwise 500 -> {"error": "服务暂时不可用"};
404 -> {"error": "未找到资源"}.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.exceptions import HTTPException

from . import auth, config, market_data, dashboard as dashboard_module

# Querystring value for range is validated when passed through; default 1y.
DASHBOARD_RANGES = {"6m", "1y", "3y", "all"}

app = FastAPI(title="Traderoff A-share Fear Greed Dashboard", docs_url=None, redoc_url=None, openapi_url=None)


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


@app.exception_handler(market_data.MarketDataError)
async def market_data_error_handler(request: Request, exc: market_data.MarketDataError):
    return JSONResponse(status_code=503, content={"error": exc.message})


@app.exception_handler(market_data.ValidationError)
async def validation_error_handler(request: Request, exc: market_data.ValidationError):
    # Validation failures become generic 500 (message NOT exposed), matching Node.
    return JSONResponse(status_code=500, content={"error": "服务暂时不可用"})


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    if isinstance(exc.detail, dict):
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"error": str(exc.detail)})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _current_user(request: Request):
    return auth.current_user(request.headers.get("cookie"))


# ---------------------------------------------------------------------------
# Data API routes
# ---------------------------------------------------------------------------


@app.get("/api/dashboard")
def api_dashboard(request: Request, range: str = "1y"):
    if range not in DASHBOARD_RANGES:
        range = "1y"  # Node used `url.searchParams.get('range') || '1y'` — unknown values fell through to rangeRows default 250.
    user = _current_user(request)
    payload = dashboard_module.dashboard(range, user)
    return JSONResponse(content=payload, headers={"Cache-Control": "no-store"})


@app.get("/api/market-environment")
def api_market_environment():
    return JSONResponse(content=market_data.market_environment(), headers={"Cache-Control": "no-store"})


@app.get("/api/market-style")
def api_market_style():
    return JSONResponse(content=market_data.market_style(), headers={"Cache-Control": "no-store"})


@app.get("/api/industry-price")
def api_industry_price():
    return JSONResponse(content=market_data.industry_price(), headers={"Cache-Control": "no-store"})


@app.get("/api/market-volume")
def api_market_volume():
    return JSONResponse(content=market_data.market_volume(), headers={"Cache-Control": "no-store"})


@app.get("/api/market-volatility")
def api_market_volatility():
    return JSONResponse(content=market_data.market_volatility(), headers={"Cache-Control": "no-store"})


@app.get("/api/market-turnover")
def api_market_turnover():
    return JSONResponse(content=market_data.market_turnover(), headers={"Cache-Control": "no-store"})


@app.get("/api/market-breadth")
def api_market_breadth():
    return JSONResponse(content=market_data.market_breadth(), headers={"Cache-Control": "no-store"})


@app.get("/api/factor-exposure")
def api_factor_exposure():
    return JSONResponse(content=market_data.factor_exposure(), headers={"Cache-Control": "no-store"})


@app.get("/api/me")
def api_me(request: Request):
    return JSONResponse(content={"user": auth.public_user(_current_user(request))}, headers={"Cache-Control": "no-store"})


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------


@app.get("/api/auth/wechat")
def api_auth_wechat(request: Request):
    state = auth.create_wechat_state()
    if config.WECHAT_AUTH_MODE == "development":
        return RedirectResponse(f"/api/auth/wechat/callback?code=development&state={auth_quote(state)}", status_code=302)
    if not config.WECHAT_APP_ID or not config.WECHAT_APP_SECRET or not config.WECHAT_REDIRECT_URI:
        return RedirectResponse("/?auth=not-configured", status_code=302)
    return RedirectResponse(auth.build_wechat_authorize_url(state), status_code=302)


@app.get("/api/auth/wechat/callback")
def api_auth_wechat_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    if not auth.consume_wechat_state(state):
        return RedirectResponse("/?auth=invalid-state", status_code=302)
    if error or not code:
        return RedirectResponse("/?auth=cancelled", status_code=302)
    if config.WECHAT_AUTH_MODE == "development":
        profile = {"openid": "development-user", "nickname": "微信测试用户", "headimgurl": ""}
    else:
        profile = auth.exchange_wechat_code(code)
    user = auth.find_or_create_wechat_user(profile)
    session_token = auth.create_session(user.id)
    # Add the Set-Cookie header to the 302 redirect (mirrors Node's Set-Cookie header).
    response = RedirectResponse("/?auth=success", status_code=302)
    response.headers["Set-Cookie"] = auth.session_cookie(session_token)
    return response


@app.post("/api/logout")
def api_logout(request: Request):
    auth.destroy_session(request.headers.get("cookie"))
    response = JSONResponse(content={"ok": True}, headers={"Cache-Control": "no-store"})
    response.headers["Set-Cookie"] = auth.clear_session_cookie()
    return response


def auth_quote(value: str) -> str:
    from urllib.parse import quote
    return quote(value, safe="")


# ---------------------------------------------------------------------------
# Static file serving with SPA fallback (mirrors serveStatic + fallback)
# ---------------------------------------------------------------------------


def _file_response(path):
    from starlette.responses import FileResponse
    if path.suffix.lower() == ".html":
        return FileResponse(path, media_type="text/html; charset=utf-8", headers={"Cache-Control": "no-cache"})
    return FileResponse(path, headers={"Cache-Control": "public, max-age=86400"})


@app.get("/{full_path:path}", include_in_schema=False)
def serve_frontend(full_path: str, request: Request):
    if request.method != "GET":
        return JSONResponse(status_code=404, content={"error": "未找到资源"})

    relative = "" if full_path in ("", "index.html") else full_path
    candidate = config.STATIC_ROOT / relative if relative else config.STATIC_ROOT / "index.html"
    if not _is_within(candidate, config.STATIC_ROOT):
        return JSONResponse(status_code=404, content={"error": "未找到资源"})

    if candidate.is_file() and full_path != "":
        return _file_response(candidate)
    # SPA fallback: unknown GET path serves index.html (mirrors `return serveStatic('/', res)`)
    index = config.STATIC_ROOT / "index.html"
    return _file_response(index)


def _is_within(path, base):
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False
