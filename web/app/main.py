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

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.exceptions import HTTPException
from pydantic import BaseModel

from . import auth, config, market_data, dashboard as dashboard_module, refresher

# Querystring value for range is validated when passed through; default 1y.
DASHBOARD_RANGES = {"6m", "1y", "3y", "all"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start the in-process market-data refresh scheduler (weekdays 21:10 SH).
    refresher.start_scheduler()
    try:
        yield
    finally:
        refresher.shutdown_scheduler()


app = FastAPI(title="Traderoff A-share Fear Greed Dashboard", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)


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


class SendEmailBody(BaseModel):
    email: str


class RegisterBody(BaseModel):
    email: str
    code: str
    password: str


class LoginBody(BaseModel):
    email: str
    password: str | None = None
    code: str | None = None


class SetPasswordBody(BaseModel):
    new_password: str


@app.post("/api/auth/email/send")
def api_send_email(body: SendEmailBody):
    try:
        code = auth.send_email_code(body.email)
    except auth.RateLimitError as exc:
        return JSONResponse(status_code=429, content={"error": str(exc)})
    dev_reveal = config.SES_DEV_REVEAL
    return JSONResponse(status_code=200, content={"ok": True, **({"code": code} if dev_reveal else {})})


@app.post("/api/auth/register")
def api_register(body: RegisterBody):
    try:
        user = auth.register(body.email, body.code, body.password)
    except auth.AuthError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})
    token = auth.create_session(user.id)
    response = JSONResponse(status_code=200, content={"ok": True})
    response.headers["Set-Cookie"] = auth.session_cookie(token)
    return response


@app.post("/api/auth/login")
def api_login(body: LoginBody):
    token = None
    if body.password:
        token = auth.login_password(body.email, body.password)
        if token is None:
            return JSONResponse(status_code=401, content={"error": "邮箱或密码错误"})
    elif body.code:
        if not auth.verify_email_code(body.email, body.code):
            return JSONResponse(status_code=400, content={"error": "验证码错误或已过期"})
        user = auth._find_user_by_email(body.email) or auth._create_user(body.email, "email-temp")
        token = auth.create_session(user.id)
    else:
        return JSONResponse(status_code=400, content={"error": "缺少登录凭证"})
    response = JSONResponse(status_code=200, content={"ok": True})
    response.headers["Set-Cookie"] = auth.session_cookie(token)
    return response


@app.post("/api/logout")
def api_logout(request: Request):
    auth.destroy_session(request.headers.get("cookie"))
    response = JSONResponse(content={"ok": True}, headers={"Cache-Control": "no-store"})
    response.headers["Set-Cookie"] = auth.clear_session_cookie()
    return response


@app.post("/api/auth/password/set")
def api_set_password(body: SetPasswordBody, request: Request):
    user = _current_user(request)
    if user is None:
        return JSONResponse(status_code=401, content={"error": "请先登录"})
    try:
        auth.set_password(user.id, body.new_password)
    except auth.AuthError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})
    return JSONResponse(status_code=200, content={"ok": True})


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
