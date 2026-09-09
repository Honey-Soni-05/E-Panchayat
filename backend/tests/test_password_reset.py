"""Password reset, issued at the Panchayat counter.

There is no email or SMS gateway here, so the reset is officer-mediated: an
officer identifies the resident against the village register and issues a
one-time code, which the resident redeems for a password of their own choosing.

Two properties carry the whole feature, and both are easy to lose:

  * an officer must not be able to reset a staff account, or a village login
    becomes a route to the block;
  * redeeming must end the sessions of whoever already held the account, or the
    reset is decoration — stateless tokens would keep them signed in for the
    week a refresh token lasts.
"""

import time

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.deps import token_is_revoked
from app.db.session import SessionLocal
from app.models import AuthAttempt, PasswordReset, User
from app.services import ratelimit

API = "/api/v1"
PASSWORD = "Test@12345"
NEW_PASSWORD = "Rebuilt@2026"
HOME = "vil_loni_kalbhor"


def _user_id(email: str) -> str:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        assert user is not None, f"no seeded account for {email}"
        return user.id


def _restore(email: str, password: str = PASSWORD) -> None:
    """Put an account back as the suite's other tests expect to find it.

    Session-scoped auth fixtures hold tokens minted before any revocation here,
    so `tokens_valid_from` is cleared as well as the password — otherwise a test
    that resets a password would sign every later test out.
    """
    from app.core.security import hash_password

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        user.hashed_password = hash_password(password)
        user.tokens_valid_from = None
        for reset in db.scalars(
            select(PasswordReset).where(PasswordReset.user_id == user.id)
        ):
            db.delete(reset)
        db.commit()


@pytest.fixture
def savita():
    """A resident of the officer's own village."""
    email = "savita@citizen.panchayat.gov.in"
    yield email, _user_id(email)
    _restore(email)


def _issue(client, headers, user_id):
    return client.post(f"{API}/auth/users/{user_id}/password-reset", headers=headers)


def _step_over_the_second_boundary() -> None:
    """Wait until the wall clock enters a new second.

    A JWT's `iat` is whole seconds, so a token minted in the same second as the
    revocation survives it — the documented overlap in `token_is_revoked`, and
    the right side to err on, since the alternative rejects the fresh token
    issued by the sign-in straight after a reset.

    A test that signs in and then revokes without crossing a second boundary is
    therefore exercising that overlap rather than revocation, and passes or
    fails on how fast the machine is. This makes the boundary explicit instead.
    Costs half a second on average, not a full one.
    """
    time.sleep(1.0 - (time.time() % 1.0) + 0.01)


# ── Finding the account to reset ─────────────────────────────────────────────

def test_an_officer_can_list_the_accounts_they_may_reset(client, officer):
    """Without this the feature is unusable: the reset takes a user id, and an
    officer at the counter with a resident in front of them had no endpoint
    that would tell them one."""
    resp = client.get(f"{API}/auth/users", headers=officer)
    assert resp.status_code == 200, resp.text
    accounts = resp.json()
    assert accounts, "an officer sees none of their own residents' accounts"
    assert all(a["role"] == "citizen" for a in accounts)
    assert all(a["villageId"] == HOME for a in accounts)


def test_the_list_offers_nothing_the_reset_would_refuse(client, officer):
    """The list and the permission check have to agree, or an officer is shown
    an account and then told they may not touch it."""
    listed = client.get(f"{API}/auth/users", headers=officer).json()
    emails = {a["email"] for a in listed}

    assert "admin@panchayat.gov.in" not in emails
    assert "officer@panchayat.gov.in" not in emails
    assert "officer.theur@panchayat.gov.in" not in emails

    for account in listed:
        resp = _issue(client, officer, account["id"])
        assert resp.status_code == 200, (
            f'{account["email"]} was listed but the reset refused it'
        )
        _restore(account["email"])


def test_an_admin_still_sees_every_account(client, admin):
    accounts = client.get(f"{API}/auth/users", headers=admin).json()
    roles = {a["role"] for a in accounts}
    assert {"admin", "officer", "citizen"} <= roles


def test_a_citizen_cannot_list_accounts(client, citizen):
    assert client.get(f"{API}/auth/users", headers=citizen).status_code == 403


# ── Issuing ──────────────────────────────────────────────────────────────────

def test_an_officer_can_issue_a_code_for_their_own_resident(client, officer, savita):
    _, user_id = savita
    resp = _issue(client, officer, user_id)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["code"]
    assert body["expiresAt"]
    assert body["userEmail"] == savita[0]


def test_the_code_is_stored_only_as_a_hash(client, officer, savita):
    _, user_id = savita
    code = _issue(client, officer, user_id).json()["code"]

    with SessionLocal() as db:
        reset = db.scalar(select(PasswordReset).where(PasswordReset.user_id == user_id))
    assert reset is not None
    assert code not in reset.hashed_code
    assert reset.hashed_code.startswith("$2")


def test_issuing_again_voids_the_earlier_code(client, officer, savita):
    """Otherwise every slip of paper ever handed out stays live."""
    email, user_id = savita
    first = _issue(client, officer, user_id).json()["code"]
    second = _issue(client, officer, user_id).json()["code"]
    assert first != second

    stale = client.post(
        f"{API}/auth/reset-password",
        json={"email": email, "code": first, "newPassword": NEW_PASSWORD},
    )
    assert stale.status_code == 400

    fresh = client.post(
        f"{API}/auth/reset-password",
        json={"email": email, "code": second, "newPassword": NEW_PASSWORD},
    )
    assert fresh.status_code == 204, fresh.text


# ── Who may reset whom ───────────────────────────────────────────────────────

def test_an_officer_cannot_reset_another_villages_resident(client, neighbour_officer, savita):
    _, user_id = savita
    assert _issue(client, neighbour_officer, user_id).status_code == 403


def test_an_officer_cannot_reset_a_staff_account(client, officer):
    """The privilege escalation this feature would otherwise hand over: an
    officer who can reset an admin owns the block."""
    assert _issue(client, officer, _user_id("admin@panchayat.gov.in")).status_code == 403
    assert (
        _issue(client, officer, _user_id("officer.theur@panchayat.gov.in")).status_code
        == 403
    )


def test_an_admin_can_reset_an_officer(client, admin):
    """Officers get locked out too, and there is nobody else to unlock them."""
    email = "officer.theur@panchayat.gov.in"
    try:
        resp = _issue(client, admin, _user_id(email))
        assert resp.status_code == 200, resp.text
    finally:
        _restore(email)


def test_a_citizen_cannot_issue_a_reset_at_all(client, citizen, savita):
    _, user_id = savita
    assert _issue(client, citizen, user_id).status_code == 403


def test_issuing_requires_a_token(client, savita):
    _, user_id = savita
    assert client.post(f"{API}/auth/users/{user_id}/password-reset").status_code == 401


def test_nobody_resets_their_own_password_this_way(client, officer):
    """Self-service would skip the identity check the whole design rests on."""
    resp = _issue(client, officer, _user_id("officer@panchayat.gov.in"))
    assert resp.status_code == 400


# ── Redeeming ────────────────────────────────────────────────────────────────

def test_a_code_sets_a_password_the_officer_never_saw(client, officer, savita):
    email, user_id = savita
    code = _issue(client, officer, user_id).json()["code"]

    redeemed = client.post(
        f"{API}/auth/reset-password",
        json={"email": email, "code": code, "newPassword": NEW_PASSWORD},
    )
    assert redeemed.status_code == 204, redeemed.text

    signed_in = client.post(
        f"{API}/auth/login", json={"email": email, "password": NEW_PASSWORD}
    )
    assert signed_in.status_code == 200, signed_in.text


def test_the_old_password_stops_working(client, officer, savita):
    email, user_id = savita
    code = _issue(client, officer, user_id).json()["code"]
    client.post(
        f"{API}/auth/reset-password",
        json={"email": email, "code": code, "newPassword": NEW_PASSWORD},
    )

    resp = client.post(f"{API}/auth/login", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 401


def test_a_code_works_only_once(client, officer, savita):
    email, user_id = savita
    code = _issue(client, officer, user_id).json()["code"]

    first = client.post(
        f"{API}/auth/reset-password",
        json={"email": email, "code": code, "newPassword": NEW_PASSWORD},
    )
    assert first.status_code == 204

    second = client.post(
        f"{API}/auth/reset-password",
        json={"email": email, "code": code, "newPassword": "Another@2026"},
    )
    assert second.status_code == 400


def test_an_expired_code_is_refused(client, officer, savita):
    from datetime import datetime, timedelta, timezone

    email, user_id = savita
    code = _issue(client, officer, user_id).json()["code"]

    with SessionLocal() as db:
        reset = db.scalar(select(PasswordReset).where(PasswordReset.user_id == user_id))
        reset.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()

    resp = client.post(
        f"{API}/auth/reset-password",
        json={"email": email, "code": code, "newPassword": NEW_PASSWORD},
    )
    assert resp.status_code == 400


def test_the_code_is_forgiving_about_how_it_is_typed(client, officer, savita):
    """It is read off a slip of paper by someone who may not use a Latin
    keyboard daily. Case and the grouping dash must not be the thing that
    fails."""
    email, user_id = savita
    code = _issue(client, officer, user_id).json()["code"]
    mangled = code.lower().replace("-", " ")

    resp = client.post(
        f"{API}/auth/reset-password",
        json={"email": email, "code": mangled, "newPassword": NEW_PASSWORD},
    )
    assert resp.status_code == 204, resp.text


def test_a_wrong_code_says_nothing_about_the_account(client, officer, savita):
    """The refusal must read the same for a real address with a wrong code and
    for an address that holds no account at all."""
    email, user_id = savita
    _issue(client, officer, user_id)

    wrong = client.post(
        f"{API}/auth/reset-password",
        json={"email": email, "code": "AAAAA-AAAAA", "newPassword": NEW_PASSWORD},
    )
    unknown = client.post(
        f"{API}/auth/reset-password",
        json={
            "email": "nobody@panchayat.gov.in",
            "code": "AAAAA-AAAAA",
            "newPassword": NEW_PASSWORD,
        },
    )
    assert wrong.status_code == unknown.status_code == 400
    assert wrong.json()["detail"] == unknown.json()["detail"]


def test_guessing_at_a_code_is_throttled(client, officer, savita, monkeypatch):
    """A code is a secret with an unlimited number of tries, which is the same
    oracle signing in was."""
    email, user_id = savita
    _issue(client, officer, user_id)

    with SessionLocal() as db:
        for attempt in db.scalars(select(AuthAttempt).where(AuthAttempt.email == email)):
            db.delete(attempt)
        db.commit()

    monkeypatch.setattr(settings, "RESET_MAX_FAILURES_PER_EMAIL", 5)
    for _ in range(5):
        resp = client.post(
            f"{API}/auth/reset-password",
            json={"email": email, "code": "BBBBB-BBBBB", "newPassword": NEW_PASSWORD},
        )
        assert resp.status_code == 400

    blocked = client.post(
        f"{API}/auth/reset-password",
        json={"email": email, "code": "BBBBB-BBBBB", "newPassword": NEW_PASSWORD},
    )
    assert blocked.status_code == 429

    with SessionLocal() as db:
        for attempt in db.scalars(select(AuthAttempt).where(AuthAttempt.email == email)):
            db.delete(attempt)
        db.commit()


# ── The part that makes a reset worth anything ───────────────────────────────

def test_redeeming_signs_out_whoever_already_had_the_account(client, officer, savita):
    """Tokens are stateless JWTs. Without revocation, resetting the password of
    a compromised account leaves the intruder signed in for a week."""
    email, user_id = savita

    intruder = client.post(
        f"{API}/auth/login", json={"email": email, "password": PASSWORD}
    ).json()
    headers = {"Authorization": f"Bearer {intruder['accessToken']}"}
    assert client.get(f"{API}/auth/me", headers=headers).status_code == 200

    _step_over_the_second_boundary()
    code = _issue(client, officer, user_id).json()["code"]
    client.post(
        f"{API}/auth/reset-password",
        json={"email": email, "code": code, "newPassword": NEW_PASSWORD},
    )

    assert client.get(f"{API}/auth/me", headers=headers).status_code == 401


def test_the_intruders_refresh_token_dies_too(client, officer, savita):
    """The access token expires in an hour anyway. The refresh token is the one
    that would keep them in for a week."""
    email, user_id = savita
    intruder = client.post(
        f"{API}/auth/login", json={"email": email, "password": PASSWORD}
    ).json()

    _step_over_the_second_boundary()
    code = _issue(client, officer, user_id).json()["code"]
    client.post(
        f"{API}/auth/reset-password",
        json={"email": email, "code": code, "newPassword": NEW_PASSWORD},
    )

    resp = client.post(
        f"{API}/auth/refresh", json={"refreshToken": intruder["refreshToken"]}
    )
    assert resp.status_code == 401


def test_changing_your_own_password_ends_your_other_sessions(client):
    """Same mechanism, reached the ordinary way."""
    email = "officer.theur@panchayat.gov.in"
    try:
        elsewhere = client.post(
            f"{API}/auth/login", json={"email": email, "password": PASSWORD}
        ).json()
        stale = {"Authorization": f"Bearer {elsewhere['accessToken']}"}

        here = client.post(
            f"{API}/auth/login", json={"email": email, "password": PASSWORD}
        ).json()
        mine = {"Authorization": f"Bearer {here['accessToken']}"}

        _step_over_the_second_boundary()
        changed = client.post(
            f"{API}/auth/change-password",
            headers=mine,
            json={"currentPassword": PASSWORD, "newPassword": NEW_PASSWORD},
        )
        assert changed.status_code == 200, changed.text

        # The caller is handed working tokens, or they would be signed out by
        # their own success.
        fresh = {"Authorization": f"Bearer {changed.json()['accessToken']}"}
        assert client.get(f"{API}/auth/me", headers=fresh).status_code == 200

        assert client.get(f"{API}/auth/me", headers=stale).status_code == 401
    finally:
        _restore(email)


def test_a_reset_is_recorded(client, officer, savita):
    """Someone else setting a resident's password is exactly the event an audit
    trail exists for."""
    email, user_id = savita
    code = _issue(client, officer, user_id).json()["code"]
    client.post(
        f"{API}/auth/reset-password",
        json={"email": email, "code": code, "newPassword": NEW_PASSWORD},
    )

    with SessionLocal() as db:
        redeemed = db.scalar(
            select(AuthAttempt)
            .where(AuthAttempt.email == email)
            .where(AuthAttempt.outcome == "reset_redeemed")
        )
        issued = db.scalar(
            select(PasswordReset).where(PasswordReset.user_id == user_id)
        )
    assert redeemed is not None
    assert issued.issued_by_id, "the officer who issued it is not recorded"


def test_the_revocation_boundary_is_exact_to_the_second():
    """Pins the rule the tests above have to dance around, without depending on
    how fast the machine is.

    A token is revoked when it was issued strictly before the revocation second.
    One minted during that same second survives, because `iat` has no finer
    resolution to compare against — and erring the other way would reject the
    token issued by the sign-in immediately following a reset.
    """
    from datetime import datetime, timezone
    from types import SimpleNamespace

    revoked_at = datetime(2026, 9, 9, 12, 0, 30, tzinfo=timezone.utc)
    user = SimpleNamespace(tokens_valid_from=revoked_at)

    second = int(revoked_at.timestamp())
    assert token_is_revoked(user, {"iat": second - 1}) is True
    assert token_is_revoked(user, {"iat": second}) is False
    assert token_is_revoked(user, {"iat": second + 1}) is False

    # Nothing revoked yet, so nothing is refused.
    assert token_is_revoked(SimpleNamespace(tokens_valid_from=None), {"iat": 0}) is False
    # A token that cannot be placed in time cannot be shown to post-date it.
    assert token_is_revoked(user, {}) is True


def test_a_naive_stored_timestamp_is_read_as_utc():
    """SQLite hands back naive datetimes where Postgres returns aware ones. If
    the naive value were read in the server's local zone, the revocation
    boundary would move by that offset — on a machine set to IST, by five and a
    half hours in the attacker's favour."""
    from datetime import datetime, timezone
    from types import SimpleNamespace

    aware = datetime(2026, 9, 9, 12, 0, 30, tzinfo=timezone.utc)
    naive = datetime(2026, 9, 9, 12, 0, 30)
    second = int(aware.timestamp())

    assert token_is_revoked(
        SimpleNamespace(tokens_valid_from=naive), {"iat": second - 1}
    ) is True
    assert token_is_revoked(
        SimpleNamespace(tokens_valid_from=naive), {"iat": second}
    ) is False


# ── The generated code itself ────────────────────────────────────────────────

def test_codes_avoid_characters_that_are_read_wrong():
    from app.core.security import CODE_EXCLUDED_CHARS, generate_reset_code

    for _ in range(200):
        code = generate_reset_code()
        assert not set(code) & set(CODE_EXCLUDED_CHARS)


def test_codes_do_not_repeat():
    from app.core.security import generate_reset_code

    assert len({generate_reset_code() for _ in range(500)}) == 500
