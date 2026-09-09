"""Sign-in throttling.

`/auth/login` verifies a password and says yes or no. Unmetered, that is a
password oracle, and these tests are what stop it becoming one again.

The suite as a whole runs with the limits raised (see `conftest`), because every
request comes from the same TestClient address and the real per-IP limit would
otherwise trip partway through and fail unrelated tests. Each test here lowers
them to realistic values for its own duration and clears the table first, so it
starts from a known count rather than from whatever the suite has done so far.
"""

import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models import AuthAttempt
from app.services import ratelimit

API = "/api/v1"
PASSWORD = "Test@12345"
VICTIM = "officer@panchayat.gov.in"


def _clear_attempts() -> None:
    with SessionLocal() as db:
        for attempt in db.scalars(select(AuthAttempt)):
            db.delete(attempt)
        db.commit()


@pytest.fixture
def strict_limits(monkeypatch):
    """Real limits, and an empty table to count from."""
    _clear_attempts()
    monkeypatch.setattr(settings, "LOGIN_MAX_FAILURES_PER_EMAIL", 5)
    monkeypatch.setattr(settings, "LOGIN_MAX_FAILURES_PER_IP", 20)
    monkeypatch.setattr(settings, "LOGIN_WINDOW_MINUTES", 15)
    yield
    _clear_attempts()


def _fail_login(client, email: str, password: str = "not-the-password"):
    return client.post(f"{API}/auth/login", json={"email": email, "password": password})


# ── The limit itself ─────────────────────────────────────────────────────────

def test_a_wrong_password_is_refused_before_the_limit(client, strict_limits):
    assert _fail_login(client, VICTIM).status_code == 401


def test_the_sixth_wrong_password_is_throttled(client, strict_limits):
    """Five guesses, then the door closes."""
    for _ in range(5):
        assert _fail_login(client, VICTIM).status_code == 401

    blocked = _fail_login(client, VICTIM)
    assert blocked.status_code == 429
    assert blocked.headers.get("Retry-After")


def test_the_throttle_outlasts_a_correct_password(client, strict_limits):
    """The point of a lockout is that the attacker's next guess does not get
    tried, whether or not it happens to be right."""
    for _ in range(5):
        _fail_login(client, VICTIM)

    resp = client.post(f"{API}/auth/login", json={"email": VICTIM, "password": PASSWORD})
    assert resp.status_code == 429


def test_locking_one_account_does_not_lock_another(client, strict_limits):
    """The per-email limit must not become a way to shut the whole office out."""
    for _ in range(6):
        _fail_login(client, VICTIM)

    resp = client.post(
        f"{API}/auth/login",
        json={"email": "admin@panchayat.gov.in", "password": PASSWORD},
    )
    assert resp.status_code == 200, resp.text


# ── It must not become an enumeration oracle ─────────────────────────────────

def test_an_unknown_address_is_throttled_the_same_as_a_real_one(client, strict_limits):
    """If only real accounts were throttled, the throttle would answer the
    question the login response carefully refuses to: whether an address is
    registered. Same status, same body, same header."""
    for _ in range(5):
        _fail_login(client, VICTIM)
        _fail_login(client, "nobody@panchayat.gov.in")

    real = _fail_login(client, VICTIM)
    unknown = _fail_login(client, "nobody@panchayat.gov.in")

    assert real.status_code == unknown.status_code == 429
    assert real.json()["detail"] == unknown.json()["detail"]


def test_the_refusal_does_not_say_which_limit_tripped(client, strict_limits):
    for _ in range(6):
        _fail_login(client, VICTIM)
    body = _fail_login(client, VICTIM).json()["detail"].lower()
    assert "email" not in body and "ip" not in body and "address" not in body


# ── What counts, and what must not ───────────────────────────────────────────

def test_a_refusal_does_not_extend_the_lockout(client, strict_limits):
    """The trap this design has to avoid: if a throttled attempt counted as a
    failure, every retry would renew the window and the lockout would never
    expire — for the honest user as much as the attacker."""
    for _ in range(5):
        _fail_login(client, VICTIM)

    for _ in range(10):
        assert _fail_login(client, VICTIM).status_code == 429

    with SessionLocal() as db:
        counted = db.scalar(
            select(func.count())
            .select_from(AuthAttempt)
            .where(AuthAttempt.outcome.in_(ratelimit.COUNTED_FAILURES))
        )
    assert counted == 5, "refusals were counted as failures"


def test_an_applicant_checking_their_own_application_is_not_throttled(client, strict_limits):
    """Someone whose account is still pending proves their password every time
    they try. Counting that as a guess would throttle them out of the one
    endpoint that tells them where their application stands."""
    email = "throttle.applicant@example.com"
    applicant_password = "Applicant@2026"

    filed = client.post(
        f"{API}/auth/register",
        json={
            "fullName": "Throttle Applicant",
            "email": email,
            "password": applicant_password,
            "villageId": "vil_loni_kalbhor",
        },
    )
    assert filed.status_code == 202, filed.text

    for _ in range(8):
        resp = client.post(
            f"{API}/auth/login", json={"email": email, "password": applicant_password}
        )
        assert resp.status_code == 403, resp.text


# ── The record it leaves ─────────────────────────────────────────────────────

def test_a_failed_sign_in_is_written_down(client, strict_limits):
    _fail_login(client, VICTIM)
    with SessionLocal() as db:
        attempt = db.scalar(
            select(AuthAttempt).where(AuthAttempt.email == VICTIM)
        )
    assert attempt is not None
    assert attempt.successful is False
    assert attempt.outcome == "bad_password"


def test_a_successful_sign_in_is_written_down_too(client, strict_limits):
    """An audit trail of only the failures cannot answer "who got in"."""
    resp = client.post(
        f"{API}/auth/login",
        json={"email": "admin@panchayat.gov.in", "password": PASSWORD},
    )
    assert resp.status_code == 200

    with SessionLocal() as db:
        attempt = db.scalar(
            select(AuthAttempt)
            .where(AuthAttempt.email == "admin@panchayat.gov.in")
            .where(AuthAttempt.successful.is_(True))
        )
    assert attempt is not None
    assert attempt.outcome == "ok"
    assert attempt.user_id


def test_no_password_is_ever_stored_in_the_record(client, strict_limits):
    """The obvious way to get this wrong is to log the attempt for debugging."""
    secret = "Hunter2-Should-Never-Appear"
    _fail_login(client, VICTIM, password=secret)

    with SessionLocal() as db:
        rows = list(db.scalars(select(AuthAttempt)))
    for row in rows:
        assert secret not in f"{row.email}{row.outcome}{row.ip or ''}"


def test_an_unknown_address_is_recorded_as_such(client, strict_limits):
    """Distinguishable in the audit trail, identical in the response."""
    _fail_login(client, "ghost@panchayat.gov.in")
    with SessionLocal() as db:
        attempt = db.scalar(
            select(AuthAttempt).where(AuthAttempt.email == "ghost@panchayat.gov.in")
        )
    assert attempt.outcome == "no_account"
    assert attempt.user_id is None


# ── Retention ────────────────────────────────────────────────────────────────

def test_pruning_drops_old_attempts_and_keeps_recent_ones(client, strict_limits):
    """This table pairs an email with an IP, so it is personal data and must not
    accumulate forever."""
    from datetime import datetime, timedelta, timezone

    _fail_login(client, VICTIM)
    with SessionLocal() as db:
        old = AuthAttempt(
            id="att_ancient_test",
            email=VICTIM,
            ip="203.0.113.9",
            successful=False,
            outcome="bad_password",
            created_at=datetime.now(timezone.utc) - timedelta(days=120),
        )
        db.add(old)
        db.commit()

        removed = ratelimit.prune(db, keep_days=90)
        assert removed == 1
        assert db.get(AuthAttempt, "att_ancient_test") is None
        assert db.scalar(select(AuthAttempt).where(AuthAttempt.email == VICTIM))
