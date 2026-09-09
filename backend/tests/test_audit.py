"""The audit trail.

It answers two questions: who touched this record, and what did this person do.
The tests are grouped that way, plus the ones that matter most — that reading
the trail is restricted, and that nothing sensitive ends up inside it.
"""

import pytest
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import AuditEvent
from app.services import audit

API = "/api/v1"
SAVITA = "cit_102"


def _clear() -> None:
    with SessionLocal() as db:
        for event in db.scalars(select(AuditEvent)):
            db.delete(event)
        db.commit()


@pytest.fixture
def clean_trail():
    _clear()
    yield
    _clear()


def _events(**filters) -> list[AuditEvent]:
    with SessionLocal() as db:
        stmt = select(AuditEvent).order_by(AuditEvent.created_at.desc())
        for field, value in filters.items():
            stmt = stmt.where(getattr(AuditEvent, field) == value)
        return list(db.scalars(stmt))


# ── Which paths name a record ────────────────────────────────────────────────

def test_a_singular_path_names_its_record():
    assert audit.identify("/api/v1/citizens/cit_102") == ("citizen", "cit_102")
    assert audit.identify("/api/v1/documents/doc_5/file") == ("document", "doc_5")
    assert audit.identify("/api/v1/grievances/griev_201") == ("grievance", "griev_201")


def test_a_collection_path_names_none():
    assert audit.identify("/api/v1/citizens") == (None, None)
    assert audit.identify("/api/v1/grievances") == (None, None)


def test_a_nested_resident_path_is_filed_under_the_resident():
    """Opening someone's documents is opening their file, and a resident asking
    who read their record should find it without knowing the route shape."""
    entity_type, entity_id = audit.identify("/api/v1/citizens/cit_102/documents")
    assert (entity_type, entity_id) == ("citizen", "cit_102")


# ── Who touched this record ──────────────────────────────────────────────────

def test_opening_a_residents_file_is_recorded(client, officer, clean_trail):
    resp = client.get(f"{API}/citizens/{SAVITA}", headers=officer)
    assert resp.status_code == 200

    events = _events(entity_type="citizen", entity_id=SAVITA)
    assert len(events) == 1
    assert events[0].action == "read"
    assert events[0].actor_email == "officer@panchayat.gov.in"
    assert events[0].actor_role == "officer"


def test_listing_residents_is_not_recorded(client, officer, clean_trail):
    """Deliberate. An officer opens the directory on every page load, and
    recording that buries the events worth finding. The trail answers "who
    opened Savita's file", not "who could have"."""
    assert client.get(f"{API}/citizens", headers=officer).status_code == 200
    assert _events(action="read") == []


def test_asking_the_assistant_is_not_recorded(client, citizen, clean_trail):
    """POST, but nothing is written and no record is named — the verb is only
    how the question travelled.

    The UI calls /ask and /context together for every question, so recording
    them wrote two rows per question and buried the events the trail exists
    for. Access to a resident's actual record still goes through /citizens/{id}
    and is recorded there.
    """
    resp = client.post(
        f"{API}/assistant/ask",
        headers=citizen,
        json={"query": "which schemes am I eligible for?", "language": "en"},
    )
    assert resp.status_code == 200, resp.text
    client.post(
        f"{API}/assistant/context",
        headers=citizen,
        json={"query": "which schemes am I eligible for?", "language": "en"},
    )

    assert _events() == [], "assistant traffic is filling the audit trail"


def test_an_ordinary_post_is_still_recorded(client, officer, clean_trail):
    """The exemption is a named list, not a rule about POSTs. Anything that
    actually writes must still land in the trail."""
    resp = client.post(
        f"{API}/grievances",
        headers=officer,
        json={
            "title": "Audit exemption boundary test",
            "description": "Filed to prove ordinary writes are still recorded.",
            "category": "Water Supply",
            "ward": 1,
        },
    )
    assert resp.status_code in (200, 201), resp.text
    assert _events(action="post"), "a real write was not recorded"


def test_a_refused_attempt_is_recorded_too(client, neighbour_officer, clean_trail):
    """An officer reaching into another village is exactly the event a trail is
    for. Recording only what succeeded would lose it."""
    resp = client.get(f"{API}/citizens/{SAVITA}", headers=neighbour_officer)
    assert resp.status_code == 403

    events = _events(entity_id=SAVITA)
    assert len(events) == 1
    assert events[0].status_code == 403
    assert events[0].actor_email == "officer.theur@panchayat.gov.in"


def test_an_unauthenticated_request_is_not_recorded(client, clean_trail):
    """There is nobody to attribute it to, and recording it would let anyone
    fill the table by hitting the API."""
    assert client.get(f"{API}/citizens/{SAVITA}").status_code == 401
    assert _events() == []


# ── What did this person do ──────────────────────────────────────────────────

def test_a_change_is_recorded_with_its_verb(client, officer, clean_trail):
    resp = client.post(
        f"{API}/grievances",
        headers=officer,
        json={
            "title": "Audit trail test complaint",
            "description": "Filed by a test to check the audit trail records it.",
            "category": "Water Supply",
            "ward": 1,
        },
    )
    assert resp.status_code in (200, 201), resp.text

    events = _events(action="post")
    assert events
    assert events[0].method == "POST"
    assert events[0].actor_email == "officer@panchayat.gov.in"


def test_the_actors_village_rides_along(client, officer, clean_trail):
    client.get(f"{API}/citizens/{SAVITA}", headers=officer)
    events = _events(entity_id=SAVITA)
    assert events[0].village_id == "vil_loni_kalbhor"


# ── What must never be in it ─────────────────────────────────────────────────

def test_no_request_body_is_stored(client, officer, clean_trail):
    """The table is kept and read later, which is the last place a password or
    a resident's income should end up."""
    secret = "Body-Content-Must-Not-Be-Logged"
    client.post(
        f"{API}/grievances",
        headers=officer,
        json={
            "title": secret,
            "description": secret,
            "category": "Water Supply",
            "ward": 1,
        },
    )

    with SessionLocal() as db:
        rows = list(db.scalars(select(AuditEvent)))
    assert rows
    for row in rows:
        blob = f"{row.path}{row.entity_id or ''}{row.actor_email or ''}"
        assert secret not in blob


def test_a_password_reset_does_not_leak_the_code_into_the_trail(client, admin, clean_trail):
    """The reset route returns a code in its response body. The trail records
    that the route was called, and must not record what it answered."""
    from app.models import User

    with SessionLocal() as db:
        target = db.scalar(
            select(User).where(User.email == "officer.theur@panchayat.gov.in")
        )
        target_id = target.id

    resp = client.post(f"{API}/auth/users/{target_id}/password-reset", headers=admin)
    assert resp.status_code == 200
    code = resp.json()["code"]

    with SessionLocal() as db:
        rows = list(db.scalars(select(AuditEvent)))
    assert rows, "the reset itself should have been recorded"
    for row in rows:
        assert code not in f"{row.path}{row.entity_id or ''}"

    # Put the account back for the rest of the suite.
    from app.core.security import hash_password

    with SessionLocal() as db:
        user = db.get(User, target_id)
        user.hashed_password = hash_password("Test@12345")
        user.tokens_valid_from = None
        db.commit()


# ── Reading it ───────────────────────────────────────────────────────────────

def test_an_admin_can_read_the_trail(client, admin, officer, clean_trail):
    client.get(f"{API}/citizens/{SAVITA}", headers=officer)

    resp = client.get(
        f"{API}/audit/events",
        headers=admin,
        params={"entityType": "citizen", "entityId": SAVITA},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body
    assert body[0]["entityId"] == SAVITA
    assert body[0]["actorEmail"] == "officer@panchayat.gov.in"


def test_an_officer_cannot_read_the_trail(client, officer):
    """It says which residents their colleagues have been looking at, which is
    more revealing than most of what it describes."""
    assert client.get(f"{API}/audit/events", headers=officer).status_code == 403


def test_a_citizen_cannot_read_the_trail(client, citizen):
    assert client.get(f"{API}/audit/events", headers=citizen).status_code == 403


def test_the_trail_is_closed_to_the_public(client):
    assert client.get(f"{API}/audit/events").status_code == 401


def test_there_is_no_way_to_delete_an_event(client, admin, clean_trail):
    """A trail its subjects can edit is not one."""
    client.get(f"{API}/citizens/{SAVITA}", headers=admin)
    event_id = _events()[0].id

    for method in (client.delete, client.put):
        resp = method(f"{API}/audit/events/{event_id}", headers=admin)
        assert resp.status_code in (404, 405), f"{method} reached something"


# ── Retention ────────────────────────────────────────────────────────────────

def test_pruning_drops_old_events_and_keeps_recent_ones(client, officer, clean_trail):
    from datetime import datetime, timedelta, timezone

    client.get(f"{API}/citizens/{SAVITA}", headers=officer)

    with SessionLocal() as db:
        db.add(
            AuditEvent(
                id="aud_ancient_test",
                actor_id=None,
                actor_email="someone@panchayat.gov.in",
                actor_role="officer",
                action="read",
                method="GET",
                path="/api/v1/citizens/cit_999",
                status_code=200,
                entity_type="citizen",
                entity_id="cit_999",
                created_at=datetime.now(timezone.utc) - timedelta(days=400),
            )
        )
        db.commit()

        removed = audit.prune(db, keep_days=365)
        assert removed == 1
        assert db.get(AuditEvent, "aud_ancient_test") is None
        assert db.scalar(select(AuditEvent).where(AuditEvent.entity_id == SAVITA))
