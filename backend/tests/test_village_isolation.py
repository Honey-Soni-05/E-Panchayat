"""Village isolation on the routes that take an ID, and the lists that were missed.

The first round of isolation tests checked the obvious lists — residents,
grievances, projects — and found them empty for a neighbouring officer. That is
necessary and it is not sufficient. A list that hides a record does nothing if
the record can still be opened, changed or deleted by anyone who knows or
guesses its ID, and the seeded IDs are `cit_102`, `griev_201`, `proj_301`.

Every test here signs in as the officer of Theur and reaches for something that
belongs to Loni Kalbhor. The seed puts all ten residents in Loni Kalbhor, which
is why the gap went unnoticed: with nobody living in Theur, "the neighbouring
officer sees an empty list" was true of the scoped endpoints and looked true of
the rest.

Anything destructive is aimed at a scratch record made for the test, so that a
failure here reports a hole without also wrecking the seed for the next test.
"""

from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import (
    Citizen,
    CitizenDocument,
    Grievance,
    Project,
    SabhaActionItem,
    User,
)

API = "/api/v1"
HOME = "vil_loni_kalbhor"
THEUR = "vil_theur"
SAVITA = "cit_102"
PASSWORD = "Test@12345"


# ── Scratch records, owned by Loni Kalbhor ───────────────────────────────────

def _delete(model, record_id: str) -> None:
    with SessionLocal() as db:
        row = db.get(model, record_id)
        if row is not None:
            db.delete(row)
            db.commit()


@pytest.fixture
def scratch_citizen(client, officer):
    record_id = f"cit_iso_{uuid4().hex[:8]}"
    created = client.post(f"{API}/citizens", headers=officer, json={
        "id": record_id, "name": "Isolation Probe", "nameMr": "चाचणी रहिवासी",
        "age": 44, "gender": "Female", "genderMr": "महिला",
        "occupation": "Tailor", "occupationMr": "शिंपी",
        "income": 60000, "ward": 2,
    })
    assert created.status_code == 201, created.text
    yield created.json()
    _delete(Citizen, record_id)


@pytest.fixture
def scratch_document(scratch_citizen):
    """Inserted directly rather than uploaded, so the test leaves no file on disk."""
    doc_id = f"doc_iso_{uuid4().hex[:8]}"
    with SessionLocal() as db:
        db.add(CitizenDocument(
            id=doc_id, citizen_id=scratch_citizen["id"],
            doc_type="Income Certificate", doc_type_mr="उत्पन्न दाखला",
            file_name="probe.pdf", status="Pending Verification",
            status_mr="पडताळणी प्रलंबित", submitted_date=date.today(),
        ))
        db.commit()
    yield doc_id
    _delete(CitizenDocument, doc_id)


@pytest.fixture
def scratch_grievance(client, officer):
    created = client.post(f"{API}/grievances", headers=officer, json={
        "title": "Isolation probe: drain blocked",
        "description": "Filed by a test to check village isolation.",
        "ward": 2, "citizenName": "Walk-in complainant", "phone": "9000000001",
    })
    assert created.status_code == 201, created.text
    yield created.json()
    _delete(Grievance, created.json()["id"])


@pytest.fixture
def scratch_project(client, officer):
    record_id = f"proj_iso_{uuid4().hex[:8]}"
    created = client.post(f"{API}/projects", headers=officer, json={
        "id": record_id, "name": "Isolation probe works", "nameMr": "चाचणी काम",
        "description": "Made by a test.", "descriptionMr": "चाचणी.",
        "progress": 10, "budget": 100000, "utilized": 10000,
        "status": "Ongoing", "statusMr": "सुरू असलेले", "ward": 2,
        "location": "Ward 2", "locationMr": "प्रभाग २",
        "latitude": 18.4884, "longitude": 74.0222,
    })
    assert created.status_code == 201, created.text
    yield created.json()
    _delete(Project, record_id)


@pytest.fixture
def scratch_action_item(client, officer):
    meeting = client.get(f"{API}/sabha/meetings", headers=officer).json()[0]
    created = client.post(
        f"{API}/sabha/meetings/{meeting['id']}/action-items",
        headers=officer,
        json={"action": "Isolation probe task", "responsible": "Gram Sevak"},
    )
    assert created.status_code == 201, created.text
    yield created.json()
    _delete(SabhaActionItem, created.json()["id"])


def _a_scheme(client, officer) -> str:
    return client.get(f"{API}/schemes", headers=officer).json()[0]["id"]


# ── Reading another village's records by ID ──────────────────────────────────

def test_a_neighbouring_officer_cannot_open_a_named_grievance(
    client, neighbour_officer, scratch_grievance
):
    """A complaint carries the complainant's name and phone number."""
    resp = client.get(
        f"{API}/grievances/{scratch_grievance['id']}", headers=neighbour_officer
    )
    assert resp.status_code == 403, f"read another village's complaint: {resp.text[:200]}"


def test_a_neighbouring_officer_cannot_open_a_named_project(
    client, neighbour_officer, scratch_project
):
    resp = client.get(f"{API}/projects/{scratch_project['id']}", headers=neighbour_officer)
    assert resp.status_code == 403


def test_a_neighbouring_officer_cannot_open_a_named_meeting(
    client, officer, neighbour_officer
):
    meeting = client.get(f"{API}/sabha/meetings", headers=officer).json()[0]
    resp = client.get(f"{API}/sabha/meetings/{meeting['id']}", headers=neighbour_officer)
    assert resp.status_code == 403


# ── Lists that were never scoped ─────────────────────────────────────────────

def test_a_neighbouring_officer_is_not_handed_every_residents_eligibility(
    client, officer, neighbour_officer
):
    """The worst of them. One request returned every resident of every village
    with the reason they passed or failed — which is their age, their income
    and their social category, written out in a sentence."""
    scheme = _a_scheme(client, officer)
    ours = client.get(f"{API}/schemes/{scheme}/eligibility", headers=officer).json()
    theirs = client.get(
        f"{API}/schemes/{scheme}/eligibility", headers=neighbour_officer
    ).json()
    assert len(ours) == 10
    assert theirs == [], f"saw {len(theirs)} residents of another village"


def test_a_neighbouring_officer_cannot_list_this_villages_documents(
    client, officer, neighbour_officer
):
    assert client.get(f"{API}/documents", headers=officer).json()
    assert client.get(f"{API}/documents", headers=neighbour_officer).json() == []


def test_a_neighbouring_officer_cannot_ask_for_one_residents_documents(
    client, neighbour_officer
):
    resp = client.get(
        f"{API}/documents", headers=neighbour_officer, params={"citizen_id": SAVITA}
    )
    assert resp.status_code == 403


def test_a_neighbouring_officer_cannot_list_this_villages_households(
    client, officer, neighbour_officer
):
    """A household row carries the name and age of everyone in it."""
    assert client.get(f"{API}/families", headers=officer).json()
    assert client.get(f"{API}/families", headers=neighbour_officer).json() == []


def test_action_items_are_scoped_to_the_village_that_made_them(
    client, officer, neighbour_officer
):
    assert client.get(f"{API}/sabha/action-items", headers=officer).json()
    assert client.get(f"{API}/sabha/action-items", headers=neighbour_officer).json() == []


def test_the_analytics_breakdowns_are_scoped_like_the_dashboard(
    client, neighbour_officer
):
    """The dashboard totals were scoped and the four charts beside them were
    not, so an officer shown zero residents was also shown their neighbour's
    grievances by ward and budgets by project."""
    get = lambda path: client.get(f"{API}/analytics/{path}", headers=neighbour_officer).json()
    assert all(bucket["value"] == 0 for bucket in get("age-distribution"))
    assert get("grievances-by-department") == []
    assert get("grievances-by-ward") == []
    assert get("project-budgets") == []


def test_the_dashboard_does_not_count_another_villages_documents_or_meetings(
    client, neighbour_officer
):
    stats = client.get(f"{API}/analytics/dashboard", headers=neighbour_officer).json()
    assert stats["pendingDocuments"] == 0
    assert stats["nextMeetingDate"] is None


def test_the_assistant_does_not_count_another_villages_documents(
    client, neighbour_officer
):
    body = client.post(
        f"{API}/assistant/context",
        headers=neighbour_officer,
        json={"query": "how many documents need verification?", "language": "en"},
    ).json()
    counted = [f for f in body["facts"] if "awaiting officer verification" in f]
    assert counted and counted[0].startswith("0 "), counted


# ── Changing another village's records ───────────────────────────────────────

def test_a_neighbouring_officer_cannot_edit_this_villages_resident(
    client, neighbour_officer, scratch_citizen
):
    """Income is one of the inputs to every eligibility decision, so editing it
    is deciding who qualifies."""
    resp = client.patch(
        f"{API}/citizens/{scratch_citizen['id']}",
        headers=neighbour_officer,
        json={"income": 1},
    )
    assert resp.status_code == 403
    with SessionLocal() as db:
        assert float(db.get(Citizen, scratch_citizen["id"]).income) == 60000


def test_a_neighbouring_officer_cannot_delete_this_villages_resident(
    client, neighbour_officer, scratch_citizen
):
    resp = client.delete(
        f"{API}/citizens/{scratch_citizen['id']}", headers=neighbour_officer
    )
    assert resp.status_code == 403
    with SessionLocal() as db:
        assert db.get(Citizen, scratch_citizen["id"]) is not None


def test_a_neighbouring_officer_cannot_rule_on_this_villages_document(
    client, neighbour_officer, scratch_document
):
    """Verifying a document is what turns 'Missing Documents' into 'Eligible'."""
    resp = client.post(
        f"{API}/documents/{scratch_document}/review",
        headers=neighbour_officer,
        json={"status": "Verified"},
    )
    assert resp.status_code == 403
    with SessionLocal() as db:
        assert db.get(CitizenDocument, scratch_document).status == "Pending Verification"


def test_a_neighbouring_officer_cannot_update_this_villages_grievance(
    client, neighbour_officer, scratch_grievance
):
    resp = client.patch(
        f"{API}/grievances/{scratch_grievance['id']}",
        headers=neighbour_officer,
        json={"status": "Resolved", "officerNotes": "Closed from next door"},
    )
    assert resp.status_code == 403
    with SessionLocal() as db:
        assert db.get(Grievance, scratch_grievance["id"]).status == "Pending"


def test_a_neighbouring_officer_cannot_change_or_delete_this_villages_project(
    client, neighbour_officer, scratch_project
):
    project_id = scratch_project["id"]
    patched = client.patch(
        f"{API}/projects/{project_id}", headers=neighbour_officer, json={"utilized": 99999}
    )
    assert patched.status_code == 403

    deleted = client.delete(f"{API}/projects/{project_id}", headers=neighbour_officer)
    assert deleted.status_code == 403
    with SessionLocal() as db:
        project = db.get(Project, project_id)
        assert project is not None
        assert float(project.utilized) == 10000


def test_a_neighbouring_officer_cannot_update_this_villages_action_item(
    client, neighbour_officer, scratch_action_item
):
    resp = client.patch(
        f"{API}/sabha/action-items/{scratch_action_item['id']}",
        headers=neighbour_officer,
        json={"status": "Completed"},
    )
    assert resp.status_code == 403
    with SessionLocal() as db:
        assert db.get(SabhaActionItem, scratch_action_item["id"]).status == "Pending"


def test_an_officer_cannot_attach_a_resident_to_another_villages_household(
    client, officer, neighbour_officer
):
    """A write that works as a read: the response to creating a resident lists
    the other members of the household they were attached to."""
    family = client.get(f"{API}/families", headers=officer).json()[0]
    record_id = f"cit_iso_{uuid4().hex[:8]}"
    resp = client.post(f"{API}/citizens", headers=neighbour_officer, json={
        "id": record_id, "name": "Probe", "nameMr": "चाचणी", "age": 30,
        "gender": "Male", "genderMr": "पुरुष", "occupation": "None",
        "occupationMr": "नाही", "income": 0, "ward": 1, "familyId": family["id"],
    })
    try:
        assert resp.status_code in (400, 403), resp.text[:300]
    finally:
        _delete(Citizen, record_id)


# ── An officer with no village must see nothing, not everything ──────────────

@pytest.fixture
def unassigned_officer(client):
    """An officer row with no village — what `POST /auth/users` used to create."""
    user_id = f"usr_iso_{uuid4().hex[:8]}"
    email = f"{user_id}@panchayat.gov.in"
    with SessionLocal() as db:
        db.add(User(
            id=user_id, email=email, hashed_password=hash_password(PASSWORD),
            full_name="Unassigned Officer", role="officer", village_id=None,
        ))
        db.commit()
    token = client.post(
        f"{API}/auth/login", json={"email": email, "password": PASSWORD}
    ).json()["accessToken"]
    yield {"Authorization": f"Bearer {token}"}
    _delete(User, user_id)


def test_an_officer_with_no_village_is_refused_rather_than_shown_the_block(
    client, unassigned_officer
):
    """'No village' used to mean 'no filter', which is the admin's view. An
    account that is missing its assignment has to fail closed."""
    for path in ("citizens", "grievances", "projects", "documents", "families"):
        resp = client.get(f"{API}/{path}", headers=unassigned_officer)
        assert resp.status_code == 403, f"/{path} answered {resp.status_code}"


def test_an_admin_must_say_which_village_a_new_officer_serves(client, admin):
    email = f"new.officer.{uuid4().hex[:6]}@panchayat.gov.in"
    base = {"email": email, "password": "Officer@2026", "fullName": "New Officer",
            "role": "officer"}

    try:
        refused = client.post(f"{API}/auth/users", headers=admin, json=base)
        assert refused.status_code == 400, refused.text

        nowhere = client.post(
            f"{API}/auth/users", headers=admin, json={**base, "villageId": "vil_nowhere"}
        )
        assert nowhere.status_code == 400, "accepted a village that does not exist"

        created = client.post(
            f"{API}/auth/users", headers=admin, json={**base, "villageId": THEUR}
        )
        assert created.status_code == 201, created.text
        assert created.json()["villageId"] == THEUR
    finally:
        with SessionLocal() as db:
            row = db.scalar(select(User).where(User.email == email))
            if row is not None:
                db.delete(row)
                db.commit()


def test_a_resident_account_made_by_an_admin_inherits_the_residents_village(
    client, admin, scratch_citizen
):
    email = f"probe.{uuid4().hex[:6]}@citizen.panchayat.gov.in"
    created = client.post(f"{API}/auth/users", headers=admin, json={
        "email": email, "password": "Resident@2026", "fullName": "Isolation Probe",
        "role": "citizen", "citizenId": scratch_citizen["id"],
    })
    try:
        assert created.status_code == 201, created.text
        assert created.json()["villageId"] == HOME
    finally:
        with SessionLocal() as db:
            row = db.scalar(select(User).where(User.email == email))
            if row is not None:
                db.delete(row)
                db.commit()


# ── The other half: nobody entitled is locked out ────────────────────────────

def test_the_home_officer_keeps_everything_the_neighbour_was_refused(
    client, officer, scratch_grievance, scratch_project
):
    meeting = client.get(f"{API}/sabha/meetings", headers=officer).json()[0]
    assert client.get(
        f"{API}/grievances/{scratch_grievance['id']}", headers=officer
    ).status_code == 200
    assert client.get(
        f"{API}/projects/{scratch_project['id']}", headers=officer
    ).status_code == 200
    assert client.get(
        f"{API}/sabha/meetings/{meeting['id']}", headers=officer
    ).status_code == 200
    assert client.get(
        f"{API}/documents", headers=officer, params={"citizen_id": SAVITA}
    ).status_code == 200


def test_an_admin_still_works_across_the_block(
    client, admin, scratch_grievance, scratch_project
):
    assert client.get(
        f"{API}/grievances/{scratch_grievance['id']}", headers=admin
    ).status_code == 200
    assert client.get(
        f"{API}/projects/{scratch_project['id']}", headers=admin
    ).status_code == 200
    assert len(client.get(f"{API}/families", headers=admin).json()) >= 5


def test_a_resident_can_still_open_their_own_villages_public_records(
    client, officer, citizen, scratch_project
):
    """Projects and Gram Sabha minutes are public within the village. Closing
    the gap between villages must not close this."""
    meeting = client.get(f"{API}/sabha/meetings", headers=officer).json()[0]
    assert client.get(
        f"{API}/projects/{scratch_project['id']}", headers=citizen
    ).status_code == 200
    assert client.get(
        f"{API}/sabha/meetings/{meeting['id']}", headers=citizen
    ).status_code == 200
