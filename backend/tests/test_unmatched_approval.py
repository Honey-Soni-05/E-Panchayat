"""An officer can approve an applicant who is not on the village register."""

import pytest
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Citizen, User
from tests.test_password_reset import API, HOME


def _apply(client, email, village):
    r = client.post(f"{API}/auth/register", json={
        "fullName": "New Applicant", "email": email, "password": "Applicant@2026",
        "phone": "9000000001", "villageId": village})
    assert r.status_code in (200, 201, 202), r.text


def _pending(client, headers, email):
    rows = client.get(f"{API}/auth/registrations", headers=headers).json()
    return next(r for r in rows if r["email"] == email)


def _remove(email):
    # Leave the shared register as other tests expect to find it.
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        citizen = db.get(Citizen, user.citizen_id)
        db.delete(user)
        db.flush()
        db.delete(citizen)
        db.commit()


@pytest.mark.parametrize("who, village, email", [
    ("officer", HOME, "newcomer.home@example.com"),
    ("neighbour_officer", "vil_theur", "newcomer.theur@example.com"),
])
def test_approving_without_a_match_creates_a_resident(client, request, who, village, email):
    headers = request.getfixturevalue(who)
    _apply(client, email, village)
    req = _pending(client, headers, email)
    r = client.post(f"{API}/auth/registrations/{req['id']}/decision", headers=headers,
                    json={"approve": True})
    assert r.status_code == 200, r.text
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        assert user.role == "citizen"
        assert db.get(Citizen, user.citizen_id).village_id == village
    login = client.post(f"{API}/auth/login", json={"email": email, "password": "Applicant@2026"})
    assert login.status_code == 200
    _remove(email)


def test_sign_in_never_asks_for_device_approval_by_default(client):
    for device in ("a", "b", "c"):
        r = client.post(f"{API}/auth/login", json={
            "email": "officer@panchayat.gov.in", "password": "Test@12345", "deviceId": device})
        assert r.status_code == 200
