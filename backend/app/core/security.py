"""Password hashing, JWT issuing/verification, and reset codes."""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Literal

import bcrypt
import jwt

from app.core.config import settings

TokenType = Literal["access", "refresh"]

# O, I, L and S are dropped, along with the digits 0 and 1 they are confused
# with; 5 stays because with S gone nothing else looks like it. A reset code is
# read off a slip of paper at a counter, and a resident who types 0 for O has
# not failed a security check — they have hit a badly chosen alphabet.
#
# 30 characters over 10 places is a little under 50 bits, far more than the five
# metered attempts at redeeming it could ever search.
_CODE_ALPHABET = "ABCDEFGHJKMNPQRTUVWXYZ23456789"
_CODE_LENGTH = 10
# Everything the alphabet deliberately excludes, named once so the test cannot
# drift from the implementation.
CODE_EXCLUDED_CHARS = "OILS01"


def as_utc(value: datetime | None) -> datetime | None:
    """Read a stored timestamp back as UTC-aware.

    Postgres returns a `timestamptz` column already aware; SQLite has no
    timezone type at all and hands back a naive value for the same column. Two
    things go wrong if that difference is ignored, and only one of them is loud:

      * comparing a naive value to an aware one raises TypeError — the loud one;
      * calling `.timestamp()` on a naive value silently reads it in the
        server's local zone, which would move a token-revocation boundary by
        the machine's UTC offset. On a server set to IST that is five and a half
        hours in which a revoked token still works.

    Everything in this schema is written as UTC, so a naive value is UTC that
    lost its label.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        # Malformed hash in the database — treat as a failed login, never a 500.
        return False


def generate_reset_code() -> str:
    """A one-time code, grouped for transcription: 'K7MPQ-4XRTV'.

    `secrets`, not `random` — this is a credential, and the default generator is
    seeded predictably enough to reconstruct.

    The dash is presentation only; `normalise_reset_code` strips it, so a
    resident who omits it or types lowercase still gets in.
    """
    raw = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))
    return f"{raw[:5]}-{raw[5:]}"


def normalise_reset_code(entered: str) -> str:
    """What the resident typed, reduced to what was generated."""
    return "".join(ch for ch in (entered or "").upper() if ch in _CODE_ALPHABET)


def _create_token(subject: str, token_type: TokenType, expires: timedelta,
                  claims: dict[str, Any] | None = None) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires,
    }
    if claims:
        payload.update(claims)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(subject: str, role: str, citizen_id: str | None = None) -> str:
    return _create_token(
        subject,
        "access",
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        {"role": role, "citizen_id": citizen_id},
    )


def create_refresh_token(subject: str) -> str:
    return _create_token(
        subject, "refresh", timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )


def decode_token(token: str, expected_type: TokenType) -> dict[str, Any]:
    """Raises jwt.PyJWTError on anything invalid — expired, tampered, wrong type."""
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError(f"Expected a {expected_type} token")
    return payload
