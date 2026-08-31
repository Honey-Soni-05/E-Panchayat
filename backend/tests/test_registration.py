"""Self-registration.

The point of these tests is not that the form works. It is that applying for
an account never produces a working account on its own, and that an officer
cannot use approval to reach outside their own village.
"""

import pytest
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Citizen, RegistrationRequest, User

API = "/api/v1"
PASSWORD = "Test@12345"
APPLICANT_PASSWORD = "Applicant@2026"


@pytest.fixture(scope="module", autouse=True)
def _clean_up_test_residents():
    """Remove the residents these tests invent.

    They live in Loni Kalbhor, and other test modules assert on that village's
    resident count. Without this the suite would pass or fail depending on the
    order pytest happened to collect the files in.
    """
    yield
    with SessionLocal() as db:
        for user in db.scalars(select(User).where(User.email.like("reg.%@example.com"))):
            db.delete(user)
        for citizen in db.scalars(select(Citizen).where(Citizen.id.like("cit_test_%"))):
            db.delete(citizen)
        for req in db.scalars(
            select(RegistrationRequest).where(RegistrationRequest.email.like("reg.%@example.com"))
        ):
            db.delete(req)
        db.commit()


def _apply(client, email: str, **overrides) -> dict:
    body = {
        "fullName": "Test Applicant",
        "email": email,
        "password": APPLICANT_PASSWORD,
        "villageId": "vil_loni_kalbhor",
    }
    body.update(overrides)
    resp = client.post(f"{API}/auth/register", json=body)
    assert resp.status_code == 202, resp.text
    return resp.json()


def _find(client, officer, email: str) -> dict | None:
    resp = client.get(f"{API}/auth/registrations", headers=officer)
    assert resp.status_code == 200, resp.text
    return next((r for r in resp.json() if r["email"] == email), None)


# ── Applying does not create an account ──────────────────────────────────────

def test_register_is_public_and_creates_only_a_pending_request(client):
    email = "reg.pending@example.com"
    body = _apply(client, email)
    assert body["status"] == "pending"

    with SessionLocal() as db:
        assert db.scalar(select(User).where(User.email == email)) is None
        req = db.scalar(select(RegistrationRequest).where(RegistrationRequest.email == email))
        assert req is not None and req.status == "pending"


def test_a_pending_applicant_cannot_sign_in(client):
    email = "reg.cannot.login@example.com"
    _apply(client, email)

    resp = client.post(
        f"{API}/auth/login", json={"email": email, "password": APPLICANT_PASSWORD}
    )
    assert resp.status_code == 403
    assert "verified" in resp.json()["detail"].lower()


def test_register_never_reveals_that_an_email_is_already_taken(client):
    """Both responses must be identical, or this endpoint becomes a way to test
    which residents hold accounts."""
    fresh = _apply(client, "reg.brand.new@example.com")
    taken = _apply(client, "officer@panchayat.gov.in")
    assert fresh == taken

    # And the existing officer account is untouched.
    resp = client.post(
        f"{API}/auth/login",
        json={"email": "officer@panchayat.gov.in", "password": PASSWORD},
    )
    assert resp.status_code == 200


def test_role_cannot_be_self_assigned(client):
    """Even if the client posts a role, registration only ever yields a citizen."""
    email = "reg.wants.admin@example.com"
    resp = client.post(
        f"{API}/auth/register",
        json={
            "fullName": "Ambitious Applicant",
            "email": email,
            "password": APPLICANT_PASSWORD,
            "role": "admin",
            "villageId": "vil_loni_kalbhor",
        },
    )
    assert resp.status_code == 202

    with SessionLocal() as db:
        citizen = db.scalar(
            select(Citizen).where(Citizen.village_id == "vil_loni_kalbhor")
        )
        req = db.scalar(select(RegistrationRequest).where(RegistrationRequest.email == email))
        assert not hasattr(req, "role")
        assert citizen is not None


# ── Only an officer sees the queue ───────────────────────────────────────────

def test_the_queue_is_closed_to_citizens_and_to_the_public(client, citizen):
    assert client.get(f"{API}/auth/registrations").status_code == 401
    assert client.get(f"{API}/auth/registrations", headers=citizen).status_code == 403


def test_an_officer_does_not_see_another_villages_applications(
    client, officer, neighbour_officer
):
    email = "reg.theur.applicant@example.com"
    _apply(client, email, villageId="vil_theur")

    assert _find(client, neighbour_officer, email) is not None
    assert _find(client, officer, email) is None


# ── Approval ─────────────────────────────────────────────────────────────────

_counter = iter(range(900, 999))


def _unclaimed_citizen(village_id: str = "vil_loni_kalbhor", name: str = "") -> Citizen:
    """A resident on the register with no portal account.

    Written into the database rather than picked out of the seed, so that a
    test which consumes a record by approving an account onto it cannot make a
    later test fail. The seed does leave two residents unclaimed — that is for
    the demo, not for these tests.
    """
    suffix = next(_counter)
    citizen = Citizen(
        id=f"cit_test_{suffix}",
        name=name or f"Testcase Resident {suffix}",
        name_mr=f"चाचणी रहिवासी {suffix}",
        age=41,
        gender="Female",
        gender_mr="स्त्री",
        occupation="Farmer",
        occupation_mr="शेतकरी",
        income=48000,
        ward=3,
        village_id=village_id,
        phone=f"98{suffix:08d}",
    )
    with SessionLocal() as db:
        db.add(citizen)
        db.commit()
        db.refresh(citizen)
        db.expunge(citizen)
    return citizen


def test_approval_creates_a_working_citizen_login_bound_to_one_record(client, officer):
    email = "reg.approve.me@example.com"
    resident = _unclaimed_citizen()
    _apply(client, email, fullName=resident.name, claimedWard=resident.ward)

    req = _find(client, officer, email)
    assert req is not None

    resp = client.post(
        f"{API}/auth/registrations/{req['id']}/decision",
        headers=officer,
        json={"approve": True, "citizenId": resident.id},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "approved"

    login = client.post(
        f"{API}/auth/login", json={"email": email, "password": APPLICANT_PASSWORD}
    )
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['accessToken']}"}

    me = client.get(f"{API}/auth/me", headers=headers).json()
    assert me["role"] == "citizen"
    assert me["citizenId"] == resident.id

    # And the new account is a citizen in every sense — no officer surface.
    assert client.get(f"{API}/auth/registrations", headers=headers).status_code == 403


def test_the_same_application_cannot_be_decided_twice(client, officer):
    email = "reg.decide.twice@example.com"
    _apply(client, email)
    req = _find(client, officer, email)

    first = client.post(
        f"{API}/auth/registrations/{req['id']}/decision",
        headers=officer,
        json={"approve": False, "reviewNote": "Not on the village register."},
    )
    assert first.status_code == 200

    second = client.post(
        f"{API}/auth/registrations/{req['id']}/decision",
        headers=officer,
        json={"approve": True, "citizenId": _unclaimed_citizen().id},
    )
    assert second.status_code == 409


def test_a_rejected_applicant_is_told_why_rather_than_left_guessing(client, officer):
    email = "reg.rejected.told@example.com"
    _apply(client, email)
    req = _find(client, officer, email)
    client.post(
        f"{API}/auth/registrations/{req['id']}/decision",
        headers=officer,
        json={"approve": False, "reviewNote": "Bring your ration card to the office."},
    )

    resp = client.post(
        f"{API}/auth/login", json={"email": email, "password": APPLICANT_PASSWORD}
    )
    assert resp.status_code == 403
    assert "ration card" in resp.json()["detail"]


def test_approving_requires_naming_the_resident_record(client, officer):
    email = "reg.no.citizen.id@example.com"
    _apply(client, email)
    req = _find(client, officer, email)

    resp = client.post(
        f"{API}/auth/registrations/{req['id']}/decision",
        headers=officer,
        json={"approve": True},
    )
    assert resp.status_code == 400

    with SessionLocal() as db:
        assert db.scalar(select(User).where(User.email == email)) is None


def test_an_officer_cannot_attach_an_account_to_another_villages_resident(
    client, neighbour_officer
):
    """The core containment check: approval must not be a way to reach across
    village boundaries.

    The Theur officer sees this application only because it names no village.
    They still must not be able to bind it to a Loni Kalbhor resident.
    """
    email = "reg.cross.village@example.com"
    _apply(client, email, villageId=None)
    req = _find(client, neighbour_officer, email)
    assert req is not None
    outsider = _unclaimed_citizen("vil_loni_kalbhor")

    resp = client.post(
        f"{API}/auth/registrations/{req['id']}/decision",
        headers=neighbour_officer,
        json={"approve": True, "citizenId": outsider.id},
    )
    assert resp.status_code == 403

    with SessionLocal() as db:
        assert db.scalar(select(User).where(User.email == email)) is None


def test_one_resident_record_cannot_have_two_accounts(client, officer):
    resident = _unclaimed_citizen()

    first_email = "reg.first.claim@example.com"
    _apply(client, first_email)
    first = _find(client, officer, first_email)
    assert (
        client.post(
            f"{API}/auth/registrations/{first['id']}/decision",
            headers=officer,
            json={"approve": True, "citizenId": resident.id},
        ).status_code
        == 200
    )

    second_email = "reg.second.claim@example.com"
    _apply(client, second_email)
    second = _find(client, officer, second_email)
    resp = client.post(
        f"{API}/auth/registrations/{second['id']}/decision",
        headers=officer,
        json={"approve": True, "citizenId": resident.id},
    )
    assert resp.status_code == 409

    with SessionLocal() as db:
        assert db.scalar(select(User).where(User.email == second_email)) is None


# ── Suggested matches ────────────────────────────────────────────────────────

def test_the_officer_is_offered_candidate_residents_not_a_blank_search(client, officer):
    resident = _unclaimed_citizen()
    email = "reg.suggest.me@example.com"
    _apply(client, email, fullName=resident.name, claimedWard=resident.ward)

    req = _find(client, officer, email)
    ids = [m["citizenId"] for m in req["suggestedMatches"]]
    assert resident.id in ids

    top = req["suggestedMatches"][0]
    assert top["reasons"]
    assert 0 < top["confidence"] <= 1


def test_candidates_already_holding_an_account_are_flagged_not_hidden(client, officer):
    """The officer needs to see the near-match and why it is unavailable,
    otherwise a duplicate application looks like a missing resident."""
    with SessionLocal() as db:
        claimed = db.scalar(
            select(Citizen)
            .join(User, User.citizen_id == Citizen.id)
            .where(Citizen.village_id == "vil_loni_kalbhor")
        )
        assert claimed is not None
        name, ward = claimed.name, claimed.ward

    email = "reg.duplicate.person@example.com"
    _apply(client, email, fullName=name, claimedWard=ward)

    req = _find(client, officer, email)
    flagged = [m for m in req["suggestedMatches"] if m["alreadyHasAccount"]]
    assert flagged, "expected the existing account holder to appear, flagged"


def test_suggestions_never_include_residents_of_another_village(client, officer):
    email = "reg.scope.suggestions@example.com"
    _apply(client, email, fullName="Sunita")

    req = _find(client, officer, email)
    with SessionLocal() as db:
        for match in req["suggestedMatches"]:
            citizen = db.get(Citizen, match["citizenId"])
            assert citizen.village_id == "vil_loni_kalbhor"


# ── The public village list ──────────────────────────────────────────────────

def test_the_sign_up_village_list_is_readable_without_a_token(client):
    resp = client.get(f"{API}/villages/public")
    assert resp.status_code == 200
    villages = resp.json()
    assert any(v["id"] == "vil_loni_kalbhor" for v in villages)


def test_the_public_village_list_exposes_names_and_nothing_else(client):
    """It has to work without a session, so it must not carry anything a
    stranger should not have."""
    villages = client.get(f"{API}/villages/public").json()
    assert villages
    for village in villages:
        assert set(village) == {"id", "name", "nameMr", "lgdCode"}


def test_the_public_list_omits_villages_with_no_gram_panchayat(client):
    """Four of these villages were absorbed into Pune Municipal Corporation.
    Offering them on a Panchayat sign-up form would be wrong."""
    ids = {v["id"] for v in client.get(f"{API}/villages/public").json()}
    with SessionLocal() as db:
        from app.models import Village

        merged = db.scalars(
            select(Village).where(Village.gram_panchayat_status != "active")
        )
        for village in merged:
            assert village.id not in ids
