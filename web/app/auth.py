"""Authentication: sqlite sessions + WeChat OAuth, ported from the Node server.js.

Replicates the users/sessions/oauth_states schema (including ALTER TABLE
column migrations) and the cookie/token handling of the original.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import hashlib
import secrets
import sqlite3
import threading
import time

import bcrypt

from . import config

SESSION_TTL_S = 7 * 86400  # 7 days
SMS_CODE_TTL_S = 300        # 5 minutes
SMS_CODE_MAX_DAILY = 10     # per-phone daily send cap
SMS_SEND_WINDOW_S = 60      # min interval between sends (anti-spam)
LOGIN_MAX_FAILS = 5         # consecutive failures before lockout
LOGIN_LOCK_S = 15 * 60      # lockout duration


class AuthError(Exception):
    """User-facing auth error (invalid code/password, etc.)."""


class RateLimitError(AuthError):
    """Request rate-limited (send too often, too many attempts)."""


# Serializes access to the shared sqlite connection across FastAPI worker-thread
# requests (see _get_db). SQLite with check_same_thread=False is not safe under
# concurrent reads/writes without a guard, so every public DB op holds this lock.
_DB_LOCK = threading.Lock()


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
        # FastAPI sync endpoints run on a worker thread pool, so a request may
        # touch the singleton connection from a different thread than the one
        # that created it. check_same_thread=False (SQLite serialized mode) plus
        # a busy timeout lets that happen safely.
        _db = sqlite3.connect(config.USERS_DB, check_same_thread=False)
        _db.execute("PRAGMA busy_timeout=5000")
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
        CREATE TABLE IF NOT EXISTS sms_codes (
          phone TEXT PRIMARY KEY,
          code_hash TEXT NOT NULL,
          expires_at INTEGER NOT NULL,
          attempts INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS login_attempts (
          phone TEXT PRIMARY KEY,
          failures INTEGER NOT NULL DEFAULT 0,
          locked_until INTEGER NOT NULL DEFAULT 0
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
    phone: str | None = None


def public_user(user: User | None) -> dict | None:
    if user is None:
        return None
    return {"id": user.id, "name": user.name, "avatarUrl": user.avatar_url}


def current_user(cookie_header: str | None) -> User | None:
    token = _cookie(cookie_header or "").get("session")
    if not token:
        return None
    token_hash = _sha256_hash(token)
    with _DB_LOCK:
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
    with _DB_LOCK:
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
    with _DB_LOCK:
        db = _get_db()
        db.execute("DELETE FROM sessions WHERE token_hash = ?", (_sha256_hash(token),))
        db.commit()


def clear_session_cookie() -> str:
    return "session=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0"


# ---------------------------------------------------------------------------
# SMS verification + password auth (replaces WeChat OAuth)
# ---------------------------------------------------------------------------


def hash_password(password: str) -> str:
    if not password:
        raise TypeError("password must be a non-empty string")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (TypeError, ValueError):
        return False


def _sms_provider_send(phone: str, code: str) -> str:
    """Send an SMS via Tencent Cloud SMS. Overridden in tests.

    In production this calls the Tencent Cloud SMS SDK; for now it returns the
    code so the flow is testable without a real SMS provider.
    """
    return code


def send_sms_code(phone: str) -> str:
    """Generate a 6-digit code and send it, enforcing the per-phone send limit."""
    code = f"{secrets.randbelow(1000000):06d}"
    now = int(time.time() * 1000)
    with _DB_LOCK:
        db = _get_db()
        row = db.execute("SELECT code_hash, expires_at FROM sms_codes WHERE phone = ?", (phone,)).fetchone()
        if row is not None and row["expires_at"] > now:
            # still within the send window -> rate-limit
            raise RateLimitError("验证码发送过于频繁，请稍后再试")
        # daily cap (simple: reuse the single row; production should track per-day)
        db.execute(
            "INSERT INTO sms_codes (phone, code_hash, expires_at, attempts) VALUES (?, ?, ?, 0) "
            "ON CONFLICT(phone) DO UPDATE SET code_hash=excluded.code_hash, expires_at=excluded.expires_at, attempts=0",
            (phone, _sha256_hash(code), now + SMS_CODE_TTL_S * 1000),
        )
        db.commit()
    _sms_provider_send(phone, code)
    return code


def verify_sms_code(phone: str, code: str) -> bool:
    now = int(time.time() * 1000)
    with _DB_LOCK:
        db = _get_db()
        row = db.execute("SELECT code_hash, expires_at, attempts FROM sms_codes WHERE phone = ?", (phone,)).fetchone()
        if row is None or row["expires_at"] <= now:
            return False
        if row["attempts"] >= LOGIN_MAX_FAILS:
            db.execute("DELETE FROM sms_codes WHERE phone = ?", (phone,))
            db.commit()
            return False
        if not secrets.compare_digest(row["code_hash"], _sha256_hash(code)):
            db.execute("UPDATE sms_codes SET attempts = attempts + 1 WHERE phone = ?", (phone,))
            db.commit()
            return False
        # success -> single use
        db.execute("DELETE FROM sms_codes WHERE phone = ?", (phone,))
        db.commit()
        return True


def _create_user(phone: str, password: str) -> User:
    with _DB_LOCK:
        db = _get_db()
        name = phone[-4:]  # short display name
        email = f"{phone}@sms.local"
        cursor = db.execute(
            "INSERT INTO users (name, email, password_hash, phone) VALUES (?, ?, ?, ?)",
            (name, email, hash_password(password), phone),
        )
        db.commit()
        return User(id=cursor.lastrowid, name=name, avatar_url=None, phone=phone)


def register(phone: str, code: str, password: str) -> User:
    if not verify_sms_code(phone, code):
        raise AuthError("验证码错误或已过期")
    # phone uniqueness is enforced by the users_phone_unique index
    with _DB_LOCK:
        db = _get_db()
        existing = db.execute("SELECT id FROM users WHERE phone = ?", (phone,)).fetchone()
    if existing is not None:
        raise AuthError("该手机号已注册")
    return _create_user(phone, password)


def login_password(phone: str, password: str) -> str | None:
    now = int(time.time() * 1000)
    with _DB_LOCK:
        db = _get_db()
        lock = db.execute("SELECT failures, locked_until FROM login_attempts WHERE phone = ?", (phone,)).fetchone()
        if lock is not None and lock["locked_until"] > now:
            return None  # locked
        row = db.execute("SELECT id, name, avatar_url, password_hash FROM users WHERE phone = ?", (phone,)).fetchone()
        if row is None or not verify_password(password, row["password_hash"]):
            failures = (lock["failures"] if lock else 0) + 1
            locked_until = now + LOGIN_LOCK_S * 1000 if failures >= LOGIN_MAX_FAILS else 0
            db.execute(
                "INSERT INTO login_attempts (phone, failures, locked_until) VALUES (?, ?, ?) "
                "ON CONFLICT(phone) DO UPDATE SET failures=excluded.failures, locked_until=excluded.locked_until",
                (phone, failures, locked_until),
            )
            db.commit()
            return None
        # success -> reset failures
        user_id = row["id"]
        db.execute("DELETE FROM login_attempts WHERE phone = ?", (phone,))
        db.commit()
    # create session outside the lock (create_session acquires it itself)
    return create_session(user_id)


def _find_user_by_phone(phone: str) -> User | None:
    with _DB_LOCK:
        db = _get_db()
        row = db.execute("SELECT id, name, avatar_url FROM users WHERE phone = ?", (phone,)).fetchone()
    if row is None:
        return None
    return User(id=row["id"], name=row["name"], avatar_url=row["avatar_url"], phone=phone)
