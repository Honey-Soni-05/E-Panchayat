"""Demo approval of resident applicants who are not on the village register."""

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Citizen, User
from tests.test_password_reset import API, HOME


def _apply(client, email, village=HOME):
    r = client.post(f"{API}/auth/register", json={
        "fullName": "Demo Applicant", "email": email, "password": "Applicant@2026",
        "phone": "9000000001", "villageId": village})
    assert r.status_code in (200, 201, 202), r.text


def _pending(client, headers, email):
    rows = client.get(f"{API}/auth/registrations", headers=headers).json()
    return next((r for r in rows if r["email"] == email), None)


def test_demo_officer_approves_applicant_not_on_register(client, officer):
    email = "newcomer.demo@example.com"
    _apply(client, email)
    req = _pending(client, officer, email)
    r = client.post(f"{API}/auth/registrations/{req['id']}/decision", headers=officer,
                    json={"approve": True})
    assert r.status_code == 200, r.text
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        citizen = db.get(Citizen, user.citizen_id)
        assert user.role == "citizen" and citizen.village_id == HOME
    login = client.post(f"{API}/auth/login", json={"email": email, "password": "Applicant@2026"})
    assert login.status_code == 200

    # Leave the shared register as other tests expect it: ten residents.
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        citizen = db.get(Citizen, user.citizen_id)
        db.delete(user)
        db.flush()
        db.delete(citizen)
        db.commit()


def test_other_officers_must_match_the_register(client, neighbour_officer):
    email = "theur.newcomer@example.com"
    _apply(client, email, village="vil_theur")
    req = _pending(client, neighbour_officer, email)
    r = client.post(f"{API}/auth/registrations/{req['id']}/decision", headers=neighbour_officer,
                    json={"approve": True})
    assert r.status_code == 400
