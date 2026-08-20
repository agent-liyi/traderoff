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
import logging
import secrets
import sqlite3
import threading
import time

import bcrypt

from . import config

logger = logging.getLogger(__name__)

SESSION_TTL_S = 7 * 86400  # 7 days
EMAIL_CODE_TTL_S = 300        # 5 minutes
EMAIL_CODE_MAX_DAILY = 10     # per-email daily send cap
EMAIL_SEND_WINDOW_S = 60      # min interval between sends (anti-spam)
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
        CREATE TABLE IF NOT EXISTS email_codes (
          email TEXT PRIMARY KEY,
          code_hash TEXT NOT NULL,
          expires_at INTEGER NOT NULL,
          attempts INTEGER NOT NULL DEFAULT 0,
          last_send_day TEXT NOT NULL DEFAULT '',
          day_sent INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS login_attempts (
          email TEXT PRIMARY KEY,
          failures INTEGER NOT NULL DEFAULT 0,
          locked_until INTEGER NOT NULL DEFAULT 0
        );
        """
    )
    # ALTER TABLE column migrations (mirror Node)
    columns = {row[1] for row in db.execute("PRAGMA table_info(users)")}
    if "avatar_url" not in columns:
        db.execute("ALTER TABLE users ADD COLUMN avatar_url TEXT")
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


def _email_provider_send(email: str, code: str) -> str:
    """Send a verification code email via Tencent Cloud SES.

    If SES credentials are not configured (dev stage), fall back to a no-op
    that returns the code so the flow remains testable.
    """
    if not (config.SES_SECRET_ID and config.SES_SECRET_KEY and config.SES_FROM_EMAIL_ADDRESS):
        logger.info("[auth] email provider not configured; verification code (dev only): %s", code)
        return code
    from tencentcloud.common import credential
    from tencentcloud.common.profile.client_profile import ClientProfile
    from tencentcloud.common.profile.http_profile import HttpProfile
    from tencentcloud.ses.v20201002 import ses_client, models as ses_models

    cred = credential.Credential(config.SES_SECRET_ID, config.SES_SECRET_KEY)
    http_profile = HttpProfile()
    http_profile.endpoint = "ses.tencentcloudapi.com"
    client_profile = ClientProfile()
    client_profile.httpProfile = http_profile
    client = ses_client.SesClient(cred, "ap-guangzhou", client_profile)
    req = ses_models.SendEmailRequest()
    req.FromEmailAddress = config.SES_FROM_EMAIL_ADDRESS
    req.Destination = [email]
    subject = "您的登录验证码"
    body = f"您的验证码是 {code}，5 分钟内有效。"
    req.Subject = subject
    # 普通邮件(纯文本):腾讯云 SES 的 Simple.Text 必须是 Base64 编码后的正文。
    import base64
    simple = ses_models.Simple()
    simple.Html = None
    simple.Text = base64.b64encode(body.encode("utf-8")).decode("ascii")
    req.Simple = simple
    client.SendEmail(req)
    logger.info("[auth] verification email sent to %s", email)
    return code


def send_email_code(email: str) -> str:
    """Generate a 6-digit code and send it, enforcing per-email rate limits."""
    code = f"{secrets.randbelow(1000000):06d}"
    now = int(time.time() * 1000)
    today = time.strftime("%Y-%m-%d", time.localtime(now / 1000))
    with _DB_LOCK:
        db = _get_db()
        row = db.execute(
            "SELECT code_hash, expires_at, last_send_day, day_sent FROM email_codes WHERE email = ?", (email,),
        ).fetchone()
        # per-day cap (anti SMS bombing)
        if row is not None and row["last_send_day"] == today and row["day_sent"] >= EMAIL_CODE_MAX_DAILY:
            raise RateLimitError("今日验证码发送次数已达上限")
        # send-window rate limit (one code per TTL window)
        if row is not None and row["expires_at"] > now:
            raise RateLimitError("验证码发送过于频繁，请稍后再试")
        day_sent = (row["day_sent"] + 1) if (row is not None and row["last_send_day"] == today) else 1
        db.execute(
            "INSERT INTO email_codes (email, code_hash, expires_at, attempts, last_send_day, day_sent) "
            "VALUES (?, ?, ?, 0, ?, ?) "
            "ON CONFLICT(email) DO UPDATE SET code_hash=excluded.code_hash, expires_at=excluded.expires_at, "
            "attempts=0, last_send_day=excluded.last_send_day, day_sent=excluded.day_sent",
            (email, _sha256_hash(code), now + EMAIL_CODE_TTL_S * 1000, today, day_sent),
        )
        db.commit()
    _email_provider_send(email, code)
    return code


def verify_email_code(email: str, code: str) -> bool:
    now = int(time.time() * 1000)
    with _DB_LOCK:
        db = _get_db()
        row = db.execute("SELECT code_hash, expires_at, attempts FROM email_codes WHERE email = ?", (email,)).fetchone()
        if row is None or row["expires_at"] <= now:
            return False
        if row["attempts"] >= LOGIN_MAX_FAILS:
            db.execute("DELETE FROM email_codes WHERE email = ?", (email,))
            db.commit()
            return False
        if not secrets.compare_digest(row["code_hash"], _sha256_hash(code)):
            db.execute("UPDATE email_codes SET attempts = attempts + 1 WHERE email = ?", (email,))
            db.commit()
            return False
        # success -> single use
        db.execute("DELETE FROM email_codes WHERE email = ?", (email,))
        db.commit()
        return True


def _create_user(email: str, password: str) -> User:
    with _DB_LOCK:
        db = _get_db()
        name = email.split("@")[0]  # short display name from email local part
        cursor = db.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, hash_password(password)),
        )
        db.commit()
        return User(id=cursor.lastrowid, name=name, avatar_url=None)


def register(email: str, code: str, password: str) -> User:
    if not verify_email_code(email, code):
        raise AuthError("验证码错误或已过期")
    # email uniqueness is enforced by the users_email_unique index
    with _DB_LOCK:
        db = _get_db()
        existing = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if existing is not None:
        raise AuthError("该邮箱已注册")
    return _create_user(email, password)


def login_password(email: str, password: str) -> str | None:
    now = int(time.time() * 1000)
    with _DB_LOCK:
        db = _get_db()
        lock = db.execute("SELECT failures, locked_until FROM login_attempts WHERE email = ?", (email,)).fetchone()
        if lock is not None and lock["locked_until"] > now:
            return None  # locked
        row = db.execute("SELECT id, name, avatar_url, password_hash FROM users WHERE email = ?", (email,)).fetchone()
        if row is None or not verify_password(password, row["password_hash"]):
            failures = (lock["failures"] if lock else 0) + 1
            locked_until = now + LOGIN_LOCK_S * 1000 if failures >= LOGIN_MAX_FAILS else 0
            db.execute(
                "INSERT INTO login_attempts (email, failures, locked_until) VALUES (?, ?, ?) "
                "ON CONFLICT(email) DO UPDATE SET failures=excluded.failures, locked_until=excluded.locked_until",
                (email, failures, locked_until),
            )
            db.commit()
            return None
        # success -> reset failures
        user_id = row["id"]
        db.execute("DELETE FROM login_attempts WHERE email = ?", (email,))
        db.commit()
    # create session outside the lock (create_session acquires it itself)
    return create_session(user_id)


def _find_user_by_email(email: str) -> User | None:
    with _DB_LOCK:
        db = _get_db()
        row = db.execute("SELECT id, name, avatar_url FROM users WHERE email = ?", (email,)).fetchone()
    if row is None:
        return None
    return User(id=row["id"], name=row["name"], avatar_url=row["avatar_url"], email=email)
