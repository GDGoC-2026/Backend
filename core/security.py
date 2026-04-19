from datetime import datetime, timedelta, timezone
import logging
import os
import platform
from jose import jwt
from passlib.context import CryptContext
from passlib.exc import UnknownHashError
from Backend.core.config import settings

logger = logging.getLogger(__name__)


def _build_password_context() -> CryptContext:
    """
    Build passlib context with a Windows workaround for argon2 import.
    argon2-cffi calls platform.machine() at import time.
    """
    if os.name != "nt":
        return CryptContext(schemes=["pbkdf2_sha256", "argon2"], deprecated="auto")

    original_machine = platform.machine
    try:
        platform.machine = lambda: "x86_64"  # type: ignore[assignment]
        return CryptContext(schemes=["pbkdf2_sha256", "argon2"], deprecated="auto")
    except Exception:
        logger.exception("Failed to initialize passlib context with argon2 support")
        return CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
    finally:
        platform.machine = original_machine  # type: ignore[assignment]


pwd_context = _build_password_context()

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except (UnknownHashError, ValueError):
        # Older hashes (e.g., argon2) or malformed values should fail auth cleanly.
        return False
    except Exception:
        logger.exception("Unexpected password verification error")
        return False


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)
