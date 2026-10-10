"""Aadhaar sign-in and self-service OTP recovery."""

import pytest
from sqlalchemy import delete

from app.core.config import settings
from app.db.session import SessionLocal
from app.models import AuthAttempt
from app.seed import demo_aadhaar
from tests.test_password_reset import API, NEW_PASSWORD, PASSWORD, _restore

EMAIL = "anandrao@citizen.panchayat.gov.in"
AADHAAR = demo_aadhaar("cit_101")


def _clear_attempts():
    with SessionLocal() as db:
        db.execute(delete(AuthAttempt).where(AuthAttempt.email.in_([EMAIL])))
        db.execute(delete(AuthAttempt).where(AuthAttempt.email.like("aadhaar:%")))
        db.commit()


@pytest.fixture(autouse=True)
def clean():
    _clear_attempts()
    yield
    _clear_attempts()
    _restore(EMAIL)


def test_sign_in_with_aadhaar(client):
    spaced = f"{AADHAAR[:4]} {AADHAAR[4:8]} {AADHAAR[8:]}"
    r = client.post(f"{API}/auth/login", json={"aadhaar": spaced, "password": PASSWORD})
    assert r.status_code == 200, r.text
    me = client.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {r.json()['accessToken']}"})
    assert me.json()["email"] == EMAIL


def test_wrong_aadhaar_password_is_refused(client):
    r = client.post(f"{API}/auth/login", json={"aadhaar": AADHAAR, "password": "nope"})
    assert r.status_code == 401
    unknown = client.post(f"{API}/auth/login", json={"aadhaar": "999988887777", "password": "nope"})
    assert unknown.status_code == 401
    assert unknown.json()["detail"] == r.json()["detail"]


def test_malformed_aadhaar_is_rejected(client):
    r = client.post(f"{API}/auth/login", json={"aadhaar": "0123", "password": "x"})
    assert r.status_code == 422


def test_otp_resets_password(client):
    sent = client.post(f"{API}/auth/forgot-password", json={"aadhaar": AADHAAR})
    assert sent.status_code == 200, sent.text
    body = sent.json()
    assert body["sentTo"] and len(body["demoOtp"]) == 6

    bad = client.post(f"{API}/auth/forgot-password/verify",
                      json={"email": EMAIL, "otp": "000000" if body["demoOtp"] != "000000" else "111111",
                            "newPassword": NEW_PASSWORD})
    assert bad.status_code == 400

    ok = client.post(f"{API}/auth/forgot-password/verify",
                     json={"email": EMAIL, "otp": body["demoOtp"], "newPassword": NEW_PASSWORD})
    assert ok.status_code == 204, ok.text
    assert client.post(f"{API}/auth/login", json={"email": EMAIL, "password": NEW_PASSWORD}).status_code == 200

    again = client.post(f"{API}/auth/forgot-password/verify",
                        json={"email": EMAIL, "otp": body["demoOtp"], "newPassword": "Another@2026"})
    assert again.status_code == 400  # single use


def test_locked_account_must_use_the_office(client):
    for _ in range(settings.LOGIN_MAX_FAILURES_PER_EMAIL):
        client.post(f"{API}/auth/login", json={"email": EMAIL, "password": "wrong"})
    r = client.post(f"{API}/auth/forgot-password", json={"email": EMAIL})
    assert r.status_code == 423
    assert "office" in r.json()["detail"]


def test_staff_cannot_self_reset(client):
    r = client.post(f"{API}/auth/forgot-password", json={"email": "officer@panchayat.gov.in"})
    assert r.status_code == 400


def test_otp_requests_are_capped(client):
    for _ in range(settings.OTP_MAX_PER_HOUR):
        assert client.post(f"{API}/auth/forgot-password", json={"email": EMAIL}).status_code == 200
    assert client.post(f"{API}/auth/forgot-password", json={"email": EMAIL}).status_code == 429
