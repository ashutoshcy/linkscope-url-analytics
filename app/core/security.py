from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from argon2 import PasswordHasher, exceptions as argon_errors
import jwt
import hmac
import secrets

from app.core.config import secret_key
from app.db.models import User

hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=2)
COOKIE_NAME = "linkscope_session"


def hash_password(password: str) -> str:
    return hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return hasher.verify(password_hash, password)
    except (argon_errors.VerifyMismatchError, argon_errors.VerificationError, argon_errors.InvalidHashError):
        return False


def make_token(user_id: int) -> tuple[str, str]:
    csrf = secrets.token_urlsafe(24)
    token = jwt.encode({"sub": str(user_id), "csrf": csrf, "exp": datetime.now(timezone.utc) + timedelta(days=7)}, secret_key(), algorithm="HS256")
    return token, csrf


def get_db(request: Request):
    session: Session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()


def get_claims(request: Request):
    auth = request.headers.get("authorization", "")
    token = auth[7:].strip() if auth.lower().startswith("bearer ") else request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Sign in to continue")
    try:
        claims = jwt.decode(token, secret_key(), algorithms=["HS256"], options={"require": ["sub", "exp", "csrf"]})
        user_id = int(claims["sub"])
    except (jwt.PyJWTError, ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Session expired or invalid") from None
    return claims, user_id, auth.lower().startswith("bearer ")


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    _, user_id, _ = get_claims(request)
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Account no longer exists")
    return user


def guard_write(request: Request):
    # Bearer clients need no CSRF token. Browser cookie clients must present
    # the session-bound token, which is not readable by cross-site attackers.
    claims, _, bearer = get_claims(request)
    if not bearer and not hmac.compare_digest(request.headers.get("x-csrf-token", ""), claims["csrf"]):
        raise HTTPException(status_code=403, detail="Missing or invalid CSRF token")


def guard_origin(request: Request):
    origin = request.headers.get("origin")
    if origin:
        from urllib.parse import urlsplit
        parsed = urlsplit(origin)
        if parsed.netloc != request.url.netloc or parsed.scheme != request.url.scheme:
            raise HTTPException(status_code=403, detail="Invalid request origin")
