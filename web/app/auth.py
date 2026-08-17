"""Authentication: sqlite sessions + WeChat OAuth, ported from the Node server.js.

Replicates the users/sessions/oauth_states schema (including ALTER TABLE
column migrations) and the cookie/token handling of the original.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse, parse_qs

import hashlib
import hmac
import secrets
import sqlite3
import time

from . import config

WECHAT_STATE_TTL_S = config.WECHAT_STATE_TTL_S
SESSION_TTL_S = 7 * 86400  # 7 days


def _sha256_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# DB singleton (mirrors the Node synchronous DatabaseSync)
# ---------------------------------------------------------------------------

_db: sqlite3.Connection | None = None


def _get_db() -> sqlite3.Connection:
    global _db
    if _db is None:
        Path(config.USERS_DB).parent.mkdir(parents=True, exist_ok=True)
        _db = sqlite3.connect(config.USERS_DB)
        _db.row_factory = sqlite3.Row
        _init_schema(_db)
    return _db


def _init_schema(db: sqlite3.Connection) -> None:
    db.execute("PRAGMA journal_mode = WAL")
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT NOT NULL,
          email TEXT NOT NULL UNIQUE,
          password_hash TEXT NOT NULL,
          created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS sessions (
          token_hash TEXT PRIMARY KEY,
          user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
          expires_at INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS oauth_states (
          state_hash TEXT PRIMARY KEY,
          expires_at INTEGER NOT NULL
        );
        """
    )
    # ALTER TABLE column migrations (mirror Node)
    columns = {row[1] for row in db.execute("PRAGMA table_info(users)")}
    if "phone" not in columns:
        db.execute("ALTER TABLE users ADD COLUMN phone TEXT")
    if "wechat_openid" not in columns:
        db.execute("ALTER TABLE users ADD COLUMN wechat_openid TEXT")
    if "avatar_url" not in columns:
        db.execute("ALTER TABLE users ADD COLUMN avatar_url TEXT")
    db.execute("CREATE UNIQUE INDEX IF NOT EXISTS users_phone_unique ON users(phone) WHERE phone IS NOT NULL")
    db.execute("CREATE UNIQUE INDEX IF NOT EXISTS users_wechat_openid_unique ON users(wechat_openid) WHERE wechat_openid IS NOT NULL")
    db.commit()


# ---------------------------------------------------------------------------
# User / session model
# ---------------------------------------------------------------------------


@dataclass
class User:
    id: int
    name: str
    avatar_url: str | None


def public_user(user: User | None) -> dict | None:
    if user is None:
        return None
    return {"id": user.id, "name": user.name, "avatarUrl": user.avatar_url}


def current_user(cookie_header: str | None) -> User | None:
    token = _cookie(cookie_header or "").get("session")
    if not token:
        return None
    token_hash = _sha256_hash(token)
    db = _get_db()
    row = db.execute(
        "SELECT users.id, users.name, users.avatar_url FROM sessions "
        "JOIN users ON users.id = sessions.user_id "
        "WHERE sessions.token_hash = ? AND sessions.expires_at > ?",
        (token_hash, int(time.time() * 1000)),
    ).fetchone()
    if row is None:
        return None
    return User(id=row["id"], name=row["name"], avatar_url=row["avatar_url"])


def _cookie(header: str) -> dict[str, str]:
    """Parse a Cookie header into a dict (mirrors parseCookies)."""
    cookies: dict[str, str] = {}
    for part in header.split(";"):
        part = part.strip()
        if "=" not in part:
            continue
        k, _, v = part.partition("=")
        cookies[k.strip()] = v.strip()
    return cookies


def _session_cookie(token: str) -> str:
    from urllib.parse import quote
    return (
        f"session={quote(token)}; HttpOnly; SameSite=Lax; Path=/; "
        f"Max-Age={SESSION_TTL_S}"
    )


def session_cookie(token: str) -> str:
    """Public wrapper for setting the session cookie on a response."""
    return _session_cookie(token)


def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    db = _get_db()
    db.execute(
        "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
        (_sha256_hash(token), user_id, int(time.time() * 1000) + SESSION_TTL_S * 1000),
    )
    db.commit()
    return token


def destroy_session(cookie_header: str | None) -> None:
    token = _cookie(cookie_header or "").get("session")
    if not token:
        return
    db = _get_db()
    db.execute("DELETE FROM sessions WHERE token_hash = ?", (_sha256_hash(token),))
    db.commit()


def clear_session_cookie() -> str:
    return "session=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0"


# ---------------------------------------------------------------------------
# WeChat OAuth
# ---------------------------------------------------------------------------


def create_wechat_state() -> str:
    state = secrets.token_urlsafe(24)
    db = _get_db()
    now = int(time.time() * 1000)
    db.execute("DELETE FROM oauth_states WHERE expires_at <= ?", (now,))
    db.execute(
        "INSERT INTO oauth_states (state_hash, expires_at) VALUES (?, ?)",
        (_sha256_hash(state), now + WECHAT_STATE_TTL_S * 1000),
    )
    db.commit()
    return state


def consume_wechat_state(state: str | None) -> bool:
    if not state:
        return False
    db = _get_db()
    now = int(time.time() * 1000)
    state_hash = _sha256_hash(state)
    row = db.execute("SELECT expires_at FROM oauth_states WHERE state_hash = ?", (state_hash,)).fetchone()
    db.execute("DELETE FROM oauth_states WHERE state_hash = ?", (state_hash,))
    db.commit()
    return bool(row and row["expires_at"] > now)


def build_wechat_authorize_url(state: str) -> str:
    params = {
        "appid": config.WECHAT_APP_ID,
        "redirect_uri": config.WECHAT_REDIRECT_URI,
        "response_type": "code",
        "scope": "snsapi_login",
        "state": state,
    }
    base = "https://open.weixin.qq.com/connect/qrconnect"
    return f"{base}?{urlencode(params)}#wechat_redirect"


def _fetch_wechat_json(url: str) -> dict:
    import httpx

    resp = httpx.get(url, headers={"Accept": "application/json"}, timeout=15)
    if resp.status_code != 200:
        raise RuntimeError(f"微信接口请求失败: {resp.status_code}")
    result = resp.json()
    if result.get("errcode"):
        raise RuntimeError(f"微信接口错误: {result['errcode']}")
    return result


def exchange_wechat_code(code: str) -> dict:
    token_params = {
        "appid": config.WECHAT_APP_ID,
        "secret": config.WECHAT_APP_SECRET,
        "code": code,
        "grant_type": "authorization_code",
    }
    token = _fetch_wechat_json(
        f"https://api.weixin.qq.com/sns/oauth2/access_token?{urlencode(token_params)}"
    )
    user_params = {
        "access_token": token["access_token"],
        "openid": token["openid"],
        "lang": "zh_CN",
    }
    return _fetch_wechat_json(
        f"https://api.weixin.qq.com/sns/userinfo?{urlencode(user_params)}"
    )


def find_or_create_wechat_user(profile: dict) -> User:
    """Finds by wechat_openid or creates a new user (mirrors findOrCreateWechatUser)."""
    db = _get_db()
    row = db.execute(
        "SELECT id, name, avatar_url FROM users WHERE wechat_openid = ?",
        (profile["openid"],),
    ).fetchone()
    if row:
        new_name = profile.get("nickname") or row["name"]
        new_avatar = profile.get("headimgurl")  # None -> nullable column
        db.execute(
            "UPDATE users SET name = ?, avatar_url = ? WHERE id = ?",
            (new_name, new_avatar, row["id"]),
        )
        db.commit()
        return User(id=row["id"], name=new_name, avatar_url=new_avatar)
    identity = _sha256_hash(profile["openid"])[:24]
    name = str(profile.get("nickname") or "微信用户")[:40]
    email = f"{identity}@wechat.local"
    avatar = profile.get("headimgurl")
    cursor = db.execute(
        "INSERT INTO users (name, email, password_hash, wechat_openid, avatar_url) "
        "VALUES (?, ?, ?, ?, ?)",
        (name, email, "wechat-oauth", profile["openid"], avatar),
    )
    db.commit()
    return User(id=cursor.lastrowid, name=name, avatar_url=avatar)
