"""The audit trail: who did what, to whose record.

Written as middleware rather than as a call at the top of each route, and that
is the whole design decision. A trail assembled from `audit.record(...)` lines
scattered through the routers is only as complete as the last person to add a
route remembered to be — and the one that gets forgotten is always the new
endpoint nobody reviewed. Here a route is recorded because it was served, so a
router added tomorrow is covered without knowing this module exists.

**What is recorded.** Every state change by an authenticated user, and every
read that names one individual record. Not list endpoints — an officer opening
the resident directory is their job and does it on every page load, so recording
that buries the events worth finding. The trail answers "who opened Savita's
file", not "who could have". That limit is stated rather than papered over.

**What is not recorded, ever.** Request bodies. The point of this table is to be
kept and read later, which is the last place a resident's income, a document's
contents, or a password being set should end up. Method, path, outcome and the
record named are enough to answer the question and nothing more.

**It must never break a request.** An audit trail that can 500 the API turns a
logging bug into an outage, so everything here is wrapped: a failure to record
is logged and swallowed. That is the right way round — losing one audit row is
bad, refusing a resident's grievance because the audit table is full is worse.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from sqlalchemy import select
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.security import decode_token
from app.db.session import SessionLocal
from app.models import AuditEvent, User

log = logging.getLogger(__name__)

# Paths whose singular form names one record. The captured id is what the event
# is filed under, so a resident can be shown everyone who opened their file.
#
# Ordered longest-first: /citizens/{id}/documents must be read as a document
# request about a citizen, not matched by the shorter /citizens/{id} first.
_ENTITY_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"/citizens/(?P<id>[^/]+)/eligibility"), "citizen"),
    (re.compile(r"/citizens/(?P<id>[^/]+)/documents"), "citizen"),
    (re.compile(r"/citizens/(?P<id>[^/]+)"), "citizen"),
    (re.compile(r"/documents/(?P<id>[^/]+)/file"), "document"),
    (re.compile(r"/documents/(?P<id>[^/]+)"), "document"),
    (re.compile(r"/grievances/(?P<id>[^/]+)"), "grievance"),
    (re.compile(r"/schemes/(?P<id>[^/]+)"), "scheme"),
    (re.compile(r"/projects/(?P<id>[^/]+)"), "project"),
    (re.compile(r"/sabha/meetings/(?P<id>[^/]+)"), "sabha_meeting"),
    (re.compile(r"/auth/users/(?P<id>[^/]+)"), "user"),
    (re.compile(r"/auth/registrations/(?P<id>[^/]+)"), "registration"),
]

# Never recorded: no user behind them, or so frequent they would drown the rest.
_IGNORED = re.compile(r"^/(health|docs|redoc|openapi\.json|favicon\.ico)")


def identify(path: str) -> tuple[str | None, str | None]:
    """Which single record this path names, if any.

    A collection path — `/citizens`, `/grievances` — returns (None, None), and
    the caller uses that to decide a plain read is not worth a row.
    """
    for pattern, entity_type in _ENTITY_PATTERNS:
        match = pattern.search(path)
        if match:
            return entity_type, match.group("id")
    return None, None


def _actor(request: Request) -> tuple[str | None, str | None]:
    """The user id in the bearer token, if the token is valid.

    Decoded here rather than reused from the route's dependency because
    middleware runs outside dependency injection. An invalid or absent token is
    not an error: the request is about to be refused anyway, and a rejected
    request has no actor to attribute.
    """
    header = request.headers.get("authorization") or ""
    if not header.lower().startswith("bearer "):
        return None, None
    try:
        payload = decode_token(header[7:].strip(), "access")
    except jwt.PyJWTError:
        return None, None
    return payload.get("sub"), payload.get("role")


def _should_record(method: str, status_code: int, entity_id: str | None) -> bool:
    # A refused request is worth recording — an officer trying to open another
    # village's resident is exactly what a trail is for — but an unauthenticated
    # one has nobody to attribute it to, and the caller drops those already.
    if status_code >= 500:
        return False
    if method in ("POST", "PUT", "PATCH", "DELETE"):
        return True
    # Reads only when they name one record.
    return method == "GET" and entity_id is not None


def record_request(
    request: Request, response: Response, actor_id: str | None, actor_role: str | None
) -> None:
    path = request.url.path
    entity_type, entity_id = identify(path)

    if not _should_record(request.method, response.status_code, entity_id):
        return

    from app.services.ratelimit import client_ip

    with SessionLocal() as db:
        actor = db.get(User, actor_id) if actor_id else None
        db.add(
            AuditEvent(
                id=f"aud_{uuid4().hex[:16]}",
                actor_id=actor.id if actor else None,
                # Denormalised so the row still says who acted after the account
                # is deleted and the foreign key goes null.
                actor_email=actor.email if actor else None,
                actor_role=actor.role if actor else actor_role,
                action="read" if request.method == "GET" else request.method.lower(),
                method=request.method,
                path=path[:500],
                status_code=response.status_code,
                entity_type=entity_type,
                entity_id=entity_id,
                village_id=actor.village_id if actor else None,
                ip=client_ip(request),
            )
        )
        db.commit()


class AuditMiddleware(BaseHTTPMiddleware):
    """Records the request after it has been served.

    After, not before, because the outcome is half the record: "an officer tried
    to open a resident in another village and was refused with 403" and "an
    officer opened a resident's file" are different events, and only the status
    code tells them apart.
    """

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        if _IGNORED.match(request.url.path) or request.method == "OPTIONS":
            return response

        try:
            actor_id, actor_role = _actor(request)
            if actor_id is not None:
                record_request(request, response, actor_id, actor_role)
        except Exception:  # noqa: BLE001 - see the module docstring
            # Never let recording an action break the action.
            log.exception("Audit write failed for %s %s", request.method, request.url.path)

        return response


def prune(db, *, keep_days: int = 365) -> int:
    """Drop events older than `keep_days`, returning how many went.

    This table says who read whose file, which is exactly the sort of record
    that should not be kept indefinitely just because it is cheap to keep. A
    year covers an audit cycle and a complaint about one.

    Nothing calls this automatically — there is no scheduler in this deployment,
    and a retention policy that nothing enforces is worse than one run by hand,
    because only one of the two is honest about what is being kept.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
    stale = list(db.scalars(select(AuditEvent).where(AuditEvent.created_at < cutoff)))
    for event in stale:
        db.delete(event)
    db.commit()
    return len(stale)
