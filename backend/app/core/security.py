from datetime import datetime, timedelta, timezone
from typing import Optional, Any
from jose import jwt, JWTError
import hashlib
import os
import bcrypt

from backend.app.core.config import settings

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_MINUTES = settings.REFRESH_TOKEN_EXPIRE_MINUTES

_BCRYPT_PREFIXES = ("$2a$", "$2b$", "$2y$")


def _verify_bcrypt(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except ValueError:
        return False


def _verify_sha256_salt(plain_password: str, hashed_password: str) -> bool:
    """Backwards-compatible verification of the legacy `salt$hex` scheme."""
    try:
        salt, stored_hash = hashed_password.split("$", 1)
        computed_hash = hashlib.sha256((salt + plain_password).encode("utf-8")).hexdigest()
        return computed_hash == stored_hash
    except Exception:
        return False


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password using bcrypt (preferred) or the legacy SHA256+salt scheme."""
    if hashed_password.startswith(_BCRYPT_PREFIXES):
        return _verify_bcrypt(plain_password, hashed_password)
    return _verify_sha256_salt(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash password using bcrypt with 12 rounds (cost 2^12)."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def create_access_token(
    subject: Optional[Any] = None,
    data: Optional[dict] = None,
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create JWT access token. Accepts either subject (user ID) or data dict."""
    if subject is not None:
        to_encode = {"sub": str(subject)}
    elif data is not None:
        to_encode = data.copy()
    else:
        to_encode = {}
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(
    subject: Optional[Any] = None,
    data: Optional[dict] = None
) -> str:
    """Create JWT refresh token. Accepts either subject (user ID) or data dict."""
    if subject is not None:
        to_encode = {"sub": str(subject)}
    elif data is not None:
        to_encode = data.copy()
    else:
        to_encode = {}
    expire = datetime.now(timezone.utc) + timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


# Alias for backwards compatibility
decode_token = decode_access_token