from __future__ import annotations

from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from jose import JWTError, jwt

from app.core.config import settings

ph = PasswordHasher(
    time_cost=settings.ARGON2_TIME_COST,
    memory_cost=settings.ARGON2_MEMORY_KIB,
    parallelism=settings.ARGON2_PARALLELISM,
)

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return ph.hash(password)


def needs_rehash(hashed: str | None) -> bool:
    """True when a stored hash used older//heavier parameters than the current policy."""
    if not hashed:
        return False
    try:
        return ph.check_needs_rehash(hashed)
    except Exception:
        return False


def verify_password(plain: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    try:
        return ph.verify(hashed, plain)
    except VerifyMismatchError:
        return False


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
