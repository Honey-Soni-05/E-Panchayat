"""Sign-in throttling, counted in the database.

`/auth/login` verifies a bcrypt hash and says yes or no. Without a limit that
is a password oracle: slow per guess, but unlimited, and a weak password falls
to a patient script. This module puts a ceiling on how many guesses one email
or one source may get inside a window.

**Why the database rather than a counter in memory.** This API runs on a free
Render instance that spins down after fifteen minutes of inactivity. An
in-process counter would be cleared by every cold start, so the throttle could
be reset by waiting rather than defeated — and the sleep window happens to be
about the length of the lockout. It would also silently stop working the day a
second instance is added, because each process would count its own share.

**What is counted.** Failures, keyed on the email exactly as it was typed. An
attempt against an address with no account counts the same as one against a
real officer. Throttling only real accounts would make the throttle itself an
enumeration oracle — fast rejections for addresses nobody holds, slow ones for
addresses somebody does.

**What it cannot do.** Someone with many source addresses still gets
`LOGIN_MAX_FAILURES_PER_EMAIL` guesses per window against a chosen account, and
someone who knows an officer's address can spend five deliberate failures to
lock it for the window. Both are documented trade-offs rather than oversights;
see the note on the settings in `core.config`.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import AuthAttempt


def client_ip(request: Request) -> str | None:
    """The caller's address, as far as it can be established.

    Behind Render the socket peer is the platform's proxy, so the address has to
    come from `X-Forwarded-For`. The header is a list that each hop appends to,
    which means the leftmost entry is whatever the client sent and can be freely
    invented; the rightmost is the one our own proxy added. Taking the rightmost
    is therefore the safer read, and the reason the per-email limit exists is
    that even this can be wrong.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        hops = [hop.strip() for hop in forwarded.split(",") if hop.strip()]
        if hops:
            return hops[-1][:64]
    if request.client and request.client.host:
        return request.client.host[:64]
    return None


# Only a genuinely wrong guess counts toward a lockout. Everything else this
# endpoint can record is a non-event for throttling, and counting it would do
# real harm:
#
#   rate_limited          counting a refusal would make the window renew itself
#                         on every retry, so a lockout would never expire — for
#                         the honest user as much as the attacker
#   registration_pending  the applicant proved their password; they are waiting
#   registration_rejected the same, with a decision already made
#   inactive              correct password, disabled account — not a guess
#
# So the counter keys on outcome rather than on `successful`, and `successful`
# is left to mean what it says for the audit trail.
COUNTED_FAILURES = ("bad_password", "no_account")


def _window_start(minutes: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(minutes=minutes)


def _count_failures(db: Session, *, since: datetime, email: str | None = None,
                    ip: str | None = None) -> int:
    stmt = (
        select(func.count())
        .select_from(AuthAttempt)
        .where(AuthAttempt.outcome.in_(COUNTED_FAILURES))
        .where(AuthAttempt.created_at >= since)
    )
    if email is not None:
        stmt = stmt.where(AuthAttempt.email == email)
    if ip is not None:
        stmt = stmt.where(AuthAttempt.ip == ip)
    return db.scalar(stmt) or 0


def _too_many(retry_after_seconds: int) -> HTTPException:
    """The same refusal regardless of which limit tripped or whether the account
    exists, so the throttle cannot be read as an answer about the account."""
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=(
            "Too many sign-in attempts. Wait a few minutes and try again, or "
            "contact the Panchayat office if you cannot get in."
        ),
        headers={"Retry-After": str(retry_after_seconds)},
    )


def check_login_allowed(db: Session, email: str, ip: str | None) -> None:
    """Raise 429 if this email or this source has failed too often lately.

    Called before the password is checked, so a throttled attempt never reaches
    bcrypt — the point is to stop spending the work, not merely to hide it.
    """
    window = settings.LOGIN_WINDOW_MINUTES
    since = _window_start(window)
    retry_after = window * 60

    if _count_failures(db, since=since, email=email) >= settings.LOGIN_MAX_FAILURES_PER_EMAIL:
        raise _too_many(retry_after)

    if ip and _count_failures(db, since=since, ip=ip) >= settings.LOGIN_MAX_FAILURES_PER_IP:
        raise _too_many(retry_after)


def check_registration_allowed(db: Session, ip: str | None) -> None:
    """Cap how many applications one source can file into the officer's queue."""
    if not ip:
        return

    since = _window_start(60)
    filed = db.scalar(
        select(func.count())
        .select_from(AuthAttempt)
        .where(AuthAttempt.ip == ip)
        .where(AuthAttempt.outcome == "registration_filed")
        .where(AuthAttempt.created_at >= since)
    ) or 0

    if filed >= settings.REGISTER_MAX_PER_IP_PER_HOUR:
        raise _too_many(3600)


def prune(db: Session, *, keep_days: int = 90) -> int:
    """Delete attempts older than `keep_days`, returning how many went.

    This table pairs an email address with a source IP and a timestamp, which is
    personal data, and it is the one table here that grows on unauthenticated
    traffic. Keeping it forever would mean holding a permanent record of every
    failed sign-in by every resident — useful to nobody and a liability to hold.

    Ninety days is long enough to investigate an incident and short enough that
    the table does not become an archive. Nothing calls this automatically:
    there is no scheduler in this deployment, so it is run from the API's shell
    or from a periodic job, and doing it by hand is better than pretending a
    retention policy is enforced when it is not.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)
    stale = list(db.scalars(select(AuthAttempt).where(AuthAttempt.created_at < cutoff)))
    for attempt in stale:
        db.delete(attempt)
    db.commit()
    return len(stale)


def record(
    db: Session,
    *,
    email: str,
    ip: str | None,
    outcome: str,
    successful: bool = False,
    user_id: str | None = None,
) -> None:
    """Write the attempt down. Commits, because it must survive the failure it
    is recording — a 401 raised straight afterwards must not roll it back."""
    db.add(
        AuthAttempt(
            id=f"att_{uuid4().hex[:16]}",
            email=email[:255],
            ip=ip,
            successful=successful,
            outcome=outcome,
            user_id=user_id,
        )
    )
    db.commit()
