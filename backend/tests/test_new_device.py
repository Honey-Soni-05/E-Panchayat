"""Sign-ins from an unrecognised device wait for the owner's approval."""

import re

import pytest
from sqlalchemy import delete, select

from app.db.session import SessionLocal
from app.models import KnownDevice, LoginChallenge, User
from tests.test_password_reset import API, PASSWORD

EMAIL = "sanjay@example.com"  # a non-demo address, so the check applies


@pytest.fixture(autouse=True)
def device_approval_on(monkeypatch):
    # The feature is switched off by default; these tests exercise it.
    from app.core.config import settings
    monkeypatch.setattr(settings, "NEW_DEVICE_APPROVAL", True)


@pytest.fixture(autouse=True)
def fresh_devices():
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == "sanjay@citizen.panchayat.gov.in"))
        if user is not None:
            user.email = EMAIL
            db.commit()

    def clear():
        with SessionLocal() as db:
            uid = db.scalar(select(User.id).where(User.email == EMAIL))
            db.execute(delete(KnownDevice).where(KnownDevice.user_id == uid))
            db.execute(delete(LoginChallenge).where(LoginChallenge.user_id == uid))
            db.commit()
    clear()
    yield
    clear()
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == EMAIL))
        user.email = "sanjay@citizen.panchayat.gov.in"
        db.commit()


def _login(client, device):
    return client.post(f"{API}/auth/login", json={
        "email": EMAIL, "password": PASSWORD, "deviceId": device, "deviceLabel": "Chrome on Windows"})


def _token_from(url):
    return re.search(r"token=([^&]+)", url).group(1)


def test_first_device_is_trusted_and_remembered(client):
    assert _login(client, "home").status_code == 200
    assert _login(client, "home").status_code == 200


def test_unknown_device_is_held_until_approved(client):
    _login(client, "home")
    held = _login(client, "stranger")
    assert held.status_code == 202
    body = held.json()
    assert "accessToken" not in body and body["sentTo"]
    cid, poll = body["challengeId"], body["pollToken"]

    assert client.get(f"{API}/auth/login-challenges/{cid}", params={"poll": poll}).json()["status"] == "pending"

    url = body["demoDecisionUrl"]
    page = client.get(f"{API}/auth/login-challenges/{cid}/decide", params={"token": _token_from(url)})
    assert "Is this you" in page.text and "Chrome on Windows" in page.text

    # The decision token is not the poll token, and vice versa.
    assert client.get(f"{API}/auth/login-challenges/{cid}", params={"poll": _token_from(url)}).status_code == 404
    client.post(f"{API}/auth/login-challenges/{cid}/decide", data={"token": poll, "action": "approve"})
    assert client.get(f"{API}/auth/login-challenges/{cid}", params={"poll": poll}).json()["status"] == "pending"

    ok = client.post(f"{API}/auth/login-challenges/{cid}/decide",
                     data={"token": _token_from(url), "action": "approve"})
    assert "approved" in ok.text
    done = client.get(f"{API}/auth/login-challenges/{cid}", params={"poll": poll}).json()
    assert done["status"] == "approved" and done["tokens"]["accessToken"]
    # Tokens are collected once; the device is now trusted.
    assert client.get(f"{API}/auth/login-challenges/{cid}", params={"poll": poll}).json()["status"] == "denied"
    assert _login(client, "stranger").status_code == 200


def test_denied_device_gets_no_tokens(client):
    _login(client, "home")
    body = _login(client, "intruder").json()
    cid, poll = body["challengeId"], body["pollToken"]
    res = client.post(f"{API}/auth/login-challenges/{cid}/decide",
                      data={"token": _token_from(body["demoDecisionUrl"]), "action": "deny"})
    assert "denied" in res.text
    out = client.get(f"{API}/auth/login-challenges/{cid}", params={"poll": poll}).json()
    assert out["status"] == "denied" and out["tokens"] is None
    assert _login(client, "intruder").status_code == 202


def test_wrong_password_from_new_device_sends_no_alert(client):
    _login(client, "home")
    r = client.post(f"{API}/auth/login", json={"email": EMAIL, "password": "nope", "deviceId": "x"})
    assert r.status_code == 401
    with SessionLocal() as db:
        assert db.scalar(select(LoginChallenge.id)) is None


def test_demo_accounts_skip_device_approval(client):
    for demo in ("officer@panchayat.gov.in", "admin@panchayat.gov.in",
                 "savita@citizen.panchayat.gov.in", "anandrao@citizen.panchayat.gov.in"):
      for device in ("laptop-1", "laptop-2", "phone"):
        r = client.post(f"{API}/auth/login", json={"email": demo, "password": PASSWORD, "deviceId": device})
        assert r.status_code == 200, r.text
