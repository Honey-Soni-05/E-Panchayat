"""Shared FastAPI dependencies: database session, current user, role guards.

This module is where role-based access control actually lives. A route that
does not depend on one of these guards is public — there is no other way in.
"""

from collections.abc import Callable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db
from app.models import User

bearer_scheme = HTTPBearer(auto_error=False)

CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if creds is None:
        raise CREDENTIALS_ERROR
    try:
        payload = decode_token(creds.credentials, "access")
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired. Sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except jwt.PyJWTError:
        raise CREDENTIALS_ERROR from None

    user = db.get(User, payload.get("sub"))
    if user is None or not user.is_active:
        raise CREDENTIALS_ERROR
    return user


def require_roles(*roles: str) -> Callable[[User], User]:
    """Guard factory. `Depends(require_roles("officer", "admin"))`."""

    allowed = set(roles)

    def _guard(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This action requires a Panchayat officer account.",
            )
        return user

    return _guard


# Convenience aliases used across the routers.
require_officer = require_roles("officer", "admin")
require_admin = require_roles("admin")


def village_scope(user: User) -> str | None:
    """Which village's records this user may see.

    Returns a village id to filter by, or None meaning "all villages".
    An officer is bound to one Gram Panchayat; an admin sees the district.
    """
    if user.role == "admin":
        return None
    return user.village_id


def assert_can_access_village(user: User, village_id: str | None) -> None:
    """Guard for routes that name a village explicitly."""
    scope = village_scope(user)
    if scope is not None and village_id is not None and scope != village_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="That record belongs to another Gram Panchayat.",
        )


def assert_can_read_citizen(user: User, citizen_id: str) -> None:
    """Officers read anyone. A citizen reads only their own file.

    This single check is what replaces the old behaviour where typing any
    citizen ID at the login screen opened that resident's record.
    """
    if user.role in ("officer", "admin"):
        return
    if user.citizen_id != citizen_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own records.",
        )
