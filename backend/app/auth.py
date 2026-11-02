# ============================================================
# CLAUSEGUARD - AUTHENTICATION
# ============================================================

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Cookie, HTTPException, status

from app.database import (
    create_session,
    delete_session,
    get_session_user_id,
    get_user_by_id,
)


# ------------------------------------------------------------
# PASSWORD HASHING
# ------------------------------------------------------------

PASSWORD_SALT_BYTES = 16
PASSWORD_HASH_BYTES = 32

SCRYPT_N = 16384
SCRYPT_R = 8
SCRYPT_P = 1


def hash_password(password: str) -> str:

    salt = secrets.token_bytes(
        PASSWORD_SALT_BYTES
    )

    password_hash = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=PASSWORD_HASH_BYTES
    )

    encoded_salt = base64.urlsafe_b64encode(
        salt
    ).decode("utf-8")

    encoded_hash = base64.urlsafe_b64encode(
        password_hash
    ).decode("utf-8")

    return (
        f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}"
        f"${encoded_salt}${encoded_hash}"
    )


def verify_password(
    password: str,
    stored_hash: str
) -> bool:

    try:

        parts = stored_hash.split("$")

        if len(parts) != 6:
            return False

        algorithm = parts[0]

        if algorithm != "scrypt":
            return False

        n = int(parts[1])
        r = int(parts[2])
        p = int(parts[3])

        salt = base64.urlsafe_b64decode(
            parts[4].encode("utf-8")
        )

        expected_hash = base64.urlsafe_b64decode(
            parts[5].encode("utf-8")
        )

        actual_hash = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=n,
            r=r,
            p=p,
            dklen=len(expected_hash)
        )

        return hmac.compare_digest(
            actual_hash,
            expected_hash
        )

    except (
        ValueError,
        TypeError,
        base64.binascii.Error
    ):
        return False


# ------------------------------------------------------------
# SESSION TOKENS
# ------------------------------------------------------------

SESSION_COOKIE_NAME = "clauseguard_session"

SESSION_DURATION_DAYS = 7


def _hash_session_token(
    token: str
) -> str:

    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


def create_login_session(
    user_id: int
) -> str:

    raw_token = secrets.token_urlsafe(48)

    token_hash = _hash_session_token(
        raw_token
    )

    expires_at = (
        datetime.now(timezone.utc)
        + timedelta(
            days=SESSION_DURATION_DAYS
        )
    ).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    create_session(
        token_hash=token_hash,
        user_id=user_id,
        expires_at=expires_at
    )

    return raw_token


def logout_session(
    token: str
) -> None:

    token_hash = _hash_session_token(
        token
    )

    delete_session(
        token_hash
    )


# ------------------------------------------------------------
# CURRENT USER
# ------------------------------------------------------------

def get_current_user_from_cookie(
    session_cookie: Optional[str]
):

    if not session_cookie:
        return None

    token_hash = _hash_session_token(
        session_cookie
    )

    user_id = get_session_user_id(
        token_hash
    )

    if user_id is None:
        return None

    return get_user_by_id(
        user_id
    )


def require_user(
    session_cookie: Optional[str] = Cookie(
        default=None,
        alias=SESSION_COOKIE_NAME
    )
):

    user = get_current_user_from_cookie(
        session_cookie
    )

    if user is None:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required."
        )

    return user