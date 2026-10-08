"""From a complaint to a finished work, and the money in between.

A resident asks for twenty streetlights. That cannot be closed from a desk: the
need has to be checked, the Panchayat has to decide, somebody has to say what it
costs, the money has to be asked for, sanctioned and arrive, the work has to be
done, and the person who asked gets to say whether it was. These tests walk that
path and, more to the point, every way of stepping off it.

Three things are pinned that are easy to get wrong and expensive when they are:

  * **No stage can be skipped and no rupee can get ahead of the one before it.**
    Funds cannot be received beyond what was approved, nor spent beyond what was
    received, and a work cannot start on money that has not arrived.
  * **Priority follows the number of residents, not the number of complaints**,
    stops at High, and never overrules an officer.
  * **Nothing here is decided by a model.** Whether a complaint is a repair or a
    request for new work is keyword rules; what looks wrong with a work is
    arithmetic on recorded figures. Each rule below is tested as the rule it is.

Everything is filed in wards 4 to 9, where the seed has no complaints, so the
counts these tests assert on are counts they created.
"""

from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app import seed as seeder
from app.core import clock
from app.db.session import SessionLocal
from app.models import Facility, Grievance, GrievanceEvent, Project, ProjectEvent, User
from app.services import audit, indexer, retrieval, works
from app.services.classifier import classify, detect_request_type, extract_quantity
from app.services.demand import boosted
from tests.conftest import API, PASSWORD

HOME = "vil_loni_kalbhor"
THEUR = "vil_theur"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _login(client, name: str) -> dict[str, str]:
    resp = client.post(f"{API}/auth/login", json={
        "email": f"{name}@citizen.panchayat.gov.in", "password": PASSWORD,
    })
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['accessToken']}"}


@pytest.fixture(scope="module")
def residents(client) -> dict[str, dict[str, str]]:
    """Five different residents of Loni Kalbhor, each signed in as themselves."""
    return {name: _login(client, name) for name in
            ("anandrao", "sanjay", "ramesh", "lata", "priyanka")}


@pytest.fixture(scope="module", autouse=True)
def _leave_no_trace():
    """Remove every complaint, work and asset this module creates.

    The database is shared by the whole run, and other files count rows in it.
    """
    with SessionLocal() as db:
        before = {
            model: set(db.scalars(select(model.id)))
            for model in (Grievance, Project, Facility)
        }
    yield
    with SessionLocal() as db:
        for model in (Facility, Grievance, Project):
            for row in db.scalars(select(model).where(model.id.notin_(before[model]))):
                db.delete(row)
        db.commit()


def _file(client, headers, title: str, description: str, ward: int, **extra) -> dict:
    resp = client.post(f"{API}/grievances", headers=headers, json={
        "title": title, "description": description, "ward": ward, **extra,
    })
    assert resp.status_code == 201, resp.text
    return resp.json()


def _grievance(client, headers, grievance_id: str) -> dict:
    resp = client.get(f"{API}/grievances/{grievance_id}", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _propose(client, headers, grievance_ids=(), **overrides) -> dict:
    body = {
        "name": "Streetlights for the canal path",
        "description": "New streetlights along the canal path.",
        "ward": 9, "location": "Ward 9, canal path",
        "grievanceIds": list(grievance_ids),
        **overrides,
    }
    resp = client.post(f"{API}/projects/proposals", headers=headers, json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _decide(client, headers, project_id: str, action: str, note: str | None = None, **extra):
    return client.post(
        f"{API}/projects/{project_id}/decisions", headers=headers,
        json={"action": action, "note": note, **extra},
    )


def _entry(client, headers, project_id: str, kind: str, amount: float, **extra):
    return client.post(
        f"{API}/projects/{project_id}/budget-entries", headers=headers,
        json={"kind": kind, "amount": amount, **extra},
    )


def _ok(resp) -> dict:
    assert resp.status_code in (200, 201), resp.text
    return resp.json()


def _project(client, headers, project_id: str) -> dict:
    return _ok(client.get(f"{API}/projects/{project_id}", headers=headers))


STAGES = ["proposed", "verified", "approved", "budget_requested",
          "budget_approved", "funds_received", "in_progress"]


def _walk_to(client, officer, project_id: str, stage: str, *, amount: float = 100_000) -> dict:
    """Take a fresh proposal forward to `stage` by the shortest legal route."""
    steps = [
        lambda: _decide(client, officer, project_id, "verify", "Checked on site."),
        lambda: _decide(client, officer, project_id, "approve", "Approved."),
        lambda: _entry(client, officer, project_id, "requested", amount),
        lambda: _entry(client, officer, project_id, "approved", amount),
        lambda: _entry(client, officer, project_id, "received", amount),
        lambda: _decide(client, officer, project_id, "start"),
    ]
    for step in steps[:STAGES.index(stage)]:
        _ok(step())
    project = _project(client, officer, project_id)
    assert project["stage"] == stage
    return project


def _flag_codes(project: dict) -> set[str]:
    return {flag["code"] for flag in project["flags"]}


# ─────────────────────────────────────────────────────────────────────────────
# A repair, or a request for something new
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("text, expected", [
    ("The streetlight near the temple is broken", "service"),
    ("Hand pump not working since Monday", "service"),
    ("Pipeline leak on the main road", "service"),
    # A repair however it is phrased: "need" does not make it new work.
    ("We need the hand pump repaired, 3 families depend on it", "service"),
    ("Please install 20 additional streetlights on the canal path", "development"),
    ("Construct a new drain along the school lane", "development"),
    ("पथदिवा बंद आहे", "service"),
    ("आमच्या गल्लीत नवीन पथदिवे बसवावेत", "development"),
])
def test_a_broken_thing_is_a_repair_and_a_missing_thing_is_new_work(text, expected):
    assert detect_request_type(text)[0] == expected


def test_need_alone_is_not_a_request_for_new_work():
    """"We need water" is a complaint about supply. "We need 5 more taps" is a
    request for five things that do not exist yet. The number is the difference."""
    assert detect_request_type("We need water in ward 2") == ("service", None)
    assert detect_request_type("We need 5 more taps") == ("development", 5)


@pytest.mark.parametrize("text, expected", [
    ("Ward 3 needs 20 streetlights, dark for 2 months", 20),
    ("Lane 4: install 6 benches", 6),
    ("No lights for 3 weeks, please provide 12", 12),
    ("प्रभाग ३ मध्ये २० पथदिवे हवेत", 20),
    ("Need streetlights in ward 7", None),
    ("About 40% of the lane is dark", None),
])
def test_the_quantity_is_not_the_ward_or_the_duration(text, expected):
    assert extract_quantity(text) == expected


@pytest.mark.parametrize("title", [
    "Need streetlights on the road in our lane",
    "Street light malfunction on main road",
])
def test_a_streetlight_is_not_a_street(title):
    """"Streetlight" contains "street", which is a Roads keyword. A complaint
    about a dark lane used to be sent to Public Works — and, because similar
    complaints are matched within a category, would not have been counted with
    its neighbours' either."""
    result = classify(title)
    assert result.category == "Electricity"
    assert "street" not in result.matched_terms


def test_sewage_in_marathi_is_not_counted_as_water():
    """सांडपाणी (sewage) contains पाणी (water)."""
    result = classify("गटारातील सांडपाणी घरासमोर साचले आहे")
    assert result.category == "Sanitation"
    assert "पाणी" not in result.matched_terms


def test_filing_records_the_kind_of_request_and_the_number_asked_for(client, residents):
    body = _file(
        client, residents["priyanka"],
        "Need 12 new streetlights behind the mill",
        "There is not one light there. Please install them.", ward=9,
    )
    assert body["requestType"] == "development"
    assert body["requestTypeMr"] == "नवीन काम"
    assert body["requestedQuantity"] == 12
    assert body["category"] == "Electricity"


def test_a_repair_is_filed_as_a_repair_with_no_quantity(client, residents):
    body = _file(
        client, residents["priyanka"],
        "Streetlight broken behind the mill", "It went off 2 nights ago.", ward=9,
    )
    assert body["requestType"] == "service"
    assert body["requestedQuantity"] is None


def test_an_officer_can_correct_what_the_rules_suggested(client, officer, residents):
    """The rules suggest; the officer decides. The correction is on the record."""
    filed = _file(
        client, residents["priyanka"], "The well area is dark",
        "Could something be done about it.", ward=9,
    )
    assert filed["requestType"] == "service"

    changed = _ok(client.patch(
        f"{API}/grievances/{filed['id']}", headers=officer,
        json={"requestType": "development", "requestedQuantity": 4},
    ))
    assert changed["requestType"] == "development"
    assert changed["requestedQuantity"] == 4

    notes = [e["note"] for e in _grievance(client, officer, filed["id"])["events"]]
    assert any("new work" in (note or "") for note in notes)


def test_the_preview_says_what_kind_of_request_it_is_without_filing_anything(
    client, residents
):
    with SessionLocal() as db:
        before = len(list(db.scalars(select(Grievance.id))))

    body = _ok(client.post(f"{API}/grievances/classify", headers=residents["lata"], json={
        "title": "Need 8 new benches at the bus stand", "description": "", "ward": 9,
    }))
    assert body["requestType"] == "development"
    assert body["requestedQuantity"] == 8
    assert body["similarCount"] == 0

    with SessionLocal() as db:
        assert len(list(db.scalars(select(Grievance.id)))) == before


# ─────────────────────────────────────────────────────────────────────────────
# More residents, higher priority
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("base, residents_reporting, expected", [
    ("Low", 1, "Low"), ("Low", 2, "Low"),
    ("Low", 3, "Medium"), ("Low", 4, "Medium"),
    ("Low", 5, "High"), ("Low", 50, "High"),
    ("Medium", 3, "High"), ("Medium", 5, "High"),
    # The ceiling. Numbers alone never reach Critical, and never lower anything.
    ("High", 50, "High"),
    ("Critical", 1, "Critical"), ("Critical", 50, "Critical"),
])
def test_the_priority_rule(base, residents_reporting, expected):
    assert boosted(base, residents_reporting) == expected


def test_priority_rises_when_three_residents_report_the_same_problem(
    client, officer, residents
):
    first = _file(
        client, residents["anandrao"], "Need new streetlights on the canal path",
        "It is dark after sunset. Please install additional streetlights.", ward=8,
    )
    second = _file(
        client, residents["sanjay"], "Install streetlights along the canal path",
        "No light on this path at all in the evening.", ward=8,
    )
    # Two residents is not yet a pattern.
    assert first["priority"] == second["priority"] == "Medium"
    assert second["similarCount"] == 1

    third = _file(
        client, residents["ramesh"], "More streetlights required on the canal path",
        "Additional streetlight poles should be installed.", ward=8,
    )
    assert third["priority"] == "High"
    assert third["similarCount"] == 2

    # The third complaint made it more urgent for the first two as well.
    for earlier in (first, second):
        detail = _grievance(client, officer, earlier["id"])
        assert detail["priority"] == "High"
        raised = [e for e in detail["events"] if e["eventType"] == "priority_changed"]
        assert len(raised) == 1
        assert raised[0]["actorName"] == "Raised automatically"
        assert "3 residents" in raised[0]["note"]


def test_five_residents_raise_it_two_levels_and_never_to_critical(
    client, officer, residents
):
    """Worded as requests, so each starts at Low: Medium at three residents,
    High at five, and there it stops."""
    ids = [
        _file(client, residents["anandrao"], "Request for garbage bins at the bus stand",
              "We would like new garbage bins installed there.", ward=7)["id"],
        _file(client, residents["sanjay"], "Request to install garbage bins near the bus stand",
              "New bins are asked for.", ward=7)["id"],
    ]
    assert {_grievance(client, officer, i)["priority"] for i in ids} == {"Low"}

    ids.append(_file(client, residents["ramesh"], "Suggest additional garbage bins at the bus stand",
                     "Garbage lies in the open.", ward=7)["id"])
    assert {_grievance(client, officer, i)["priority"] for i in ids} == {"Medium"}

    # Someone who came to the office instead. No resident record behind the
    # complaint, so they count as a person of their own.
    ids.append(_file(client, officer, "Request for more garbage bins, bus stand",
                     "New garbage bins needed.", ward=7, citizenName="Walk-in complainant")["id"])
    assert {_grievance(client, officer, i)["priority"] for i in ids} == {"Medium"}

    ids.append(_file(client, residents["lata"], "Request for garbage bins by the bus stand",
                     "Please install new garbage bins.", ward=7)["id"])
    assert {_grievance(client, officer, i)["priority"] for i in ids} == {"High"}

    # And however many more arrive.
    ids.append(_file(client, residents["priyanka"], "Request for garbage bins, bus stand",
                     "We would like new garbage bins.", ward=7)["id"])
    assert {_grievance(client, officer, i)["priority"] for i in ids} == {"High"}


def test_numbers_alone_never_make_a_complaint_critical(client, officer, residents):
    """Critical is kept for danger — contamination, a live wire, a collapse. A
    drinking-water complaint already starts at High, and five residents asking
    for the same tap leave it there: if popularity could reach Critical, the
    word would stop meaning what it says."""
    filed = [
        _file(client, residents[name], "Need a new public tap at the chowk",
              "Please install an additional tap for drinking water.", ward=5)
        for name in ("anandrao", "sanjay", "ramesh", "lata", "priyanka")
    ]
    assert filed[-1]["similarCount"] == 4
    for complaint in filed:
        detail = _grievance(client, officer, complaint["id"])
        assert detail["priority"] == "High"
        assert "priority_changed" not in [e["eventType"] for e in detail["events"]]


def test_one_resident_filing_three_times_is_one_resident(client, residents):
    """The count is of people. Otherwise the way to be heard is to file twice."""
    filed = [
        _file(client, residents["lata"], f"Pothole on the mill path ({n})",
              "A deep pothole just after the bend.", ward=6)
        for n in range(3)
    ]
    assert [g["priority"] for g in filed] == ["Medium", "Medium", "Medium"]
    assert [g["similarCount"] for g in filed] == [0, 0, 0]


def test_a_priority_an_officer_set_is_not_overruled_by_numbers(client, officer, residents):
    first = _file(
        client, residents["anandrao"], "Need new streetlights at the chowk",
        "Please install additional streetlights at the chowk.", ward=5,
    )
    _ok(client.patch(f"{API}/grievances/{first['id']}", headers=officer,
                     json={"priority": "Low"}))

    others = [
        _file(client, residents[name], "Install new streetlights at the chowk",
              "Additional streetlights are needed at the chowk.", ward=5)
        for name in ("sanjay", "ramesh")
    ]

    assert _grievance(client, officer, first["id"])["priority"] == "Low"
    assert {_grievance(client, officer, g["id"])["priority"] for g in others} == {"High"}


def test_a_problem_already_resolved_does_not_count_towards_a_new_one(
    client, officer, residents
):
    old = _file(
        client, residents["anandrao"], "Need new streetlights at the ghat",
        "Please install streetlights at the ghat.", ward=6,
    )
    _ok(client.patch(f"{API}/grievances/{old['id']}", headers=officer,
                     json={"status": "Resolved"}))

    later = [
        _file(client, residents[name], "Install new streetlights at the ghat",
              "Additional streetlights are needed at the ghat.", ward=6)
        for name in ("sanjay", "ramesh")
    ]
    assert [g["priority"] for g in later] == ["Medium", "Medium"]
    assert later[-1]["similarCount"] == 1


def test_the_same_problem_in_another_ward_is_another_problem(client, residents):
    """Ward 8 already has three residents asking for streetlights."""
    elsewhere = _file(
        client, residents["lata"], "Need new streetlights on the canal path",
        "Please install additional streetlights.", ward=4,
    )
    assert elsewhere["priority"] == "Medium"
    assert elsewhere["similarCount"] == 0


def test_a_resident_is_told_how_many_others_not_who(client, officer, residents):
    mine = _file(
        client, residents["anandrao"], "Need a new footpath to the bus stop",
        "Please construct a footpath.", ward=9,
    )
    _file(client, residents["sanjay"], "Construct a new footpath to the bus stop",
          "A footpath should be built.", ward=9)

    # Their own list carries the count...
    listed = client.get(f"{API}/grievances", headers=residents["anandrao"]).json()
    assert {g["citizenName"] for g in listed} == {"Anandrao Patil"}
    assert next(g for g in listed if g["id"] == mine["id"])["similarCount"] == 1

    # ...and the list of who the others are is for the office.
    refused = client.get(f"{API}/grievances/{mine['id']}/similar", headers=residents["anandrao"])
    assert refused.status_code == 403

    similar = _ok(client.get(f"{API}/grievances/{mine['id']}/similar", headers=officer))
    assert [g["citizenName"] for g in similar] == ["Sanjay Patil"]


def test_the_preview_tells_a_resident_their_neighbours_already_reported_it(
    client, residents
):
    """Ward 8 again: three residents, none of them Priyanka."""
    body = _ok(client.post(f"{API}/grievances/classify", headers=residents["priyanka"], json={
        "title": "Please install streetlights on the canal path",
        "description": "", "ward": 8,
    }))
    assert body["similarCount"] == 3


# ─────────────────────────────────────────────────────────────────────────────
# From complaints to a proposal
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def two_complaints(client, officer, residents) -> list[dict]:
    return [
        _file(client, residents["lata"], "Need 5 new streetlights by the old well",
              "Please install them along the path.", ward=9,
              latitude=18.4871, longitude=74.0252),
        _file(client, officer, "Install new streetlights by the old well",
              "Recorded at the counter.", ward=9, citizenName="Walk-in complainant"),
    ]


@pytest.fixture
def proposal(client, officer, two_complaints) -> dict:
    return _propose(
        client, officer, [g["id"] for g in two_complaints],
        unitsPlanned=5, unitLabel="streetlights", unitLabelMr="पथदिवे",
        assetType="streetlight",
    )


def test_a_proposal_starts_with_no_money_and_no_approval(proposal):
    assert proposal["stage"] == "proposed"
    assert proposal["stageIndex"] == 1 and proposal["stageTotal"] == 8
    assert proposal["status"] == "Planned"
    assert proposal["statusMr"] == "नियोजित"
    assert proposal["budget"] == 0 and proposal["utilized"] == 0
    assert proposal["finance"]["approved"] is None
    assert proposal["category"] == "Electricity"  # taken from the first complaint
    assert proposal["villageId"] == HOME
    assert proposal["events"][0]["eventType"] == "proposed"


def test_a_proposal_takes_its_location_from_the_complaint(proposal):
    """An officer turning a complaint into a proposal should not have to look
    up coordinates to do it."""
    assert (proposal["latitude"], proposal["longitude"]) == (18.4871, 74.0252)


def test_a_proposal_with_no_located_complaint_falls_back_to_the_village_centre(
    client, officer
):
    project = _propose(client, officer, name="A work with no complaint behind it")
    village = client.get(f"{API}/villages/current", headers=officer).json()
    assert (project["latitude"], project["longitude"]) == (
        village["latitude"], village["longitude"],
    )


def test_an_officer_can_give_the_approximate_cost_with_the_proposal(client, officer):
    """The figure is the officer's own, typed in, and lands in the ledger as
    the first estimate. Nothing in this system produces a cost."""
    project = _propose(
        client, officer, name="20 streetlights on the school road",
        estimate=400_000, estimateNote="Poles, fittings, cabling and labour.",
    )
    assert project["stage"] == "proposed"          # an estimate decides nothing
    assert project["finance"]["estimated"] == 400_000
    assert project["finance"]["approved"] is None and project["budget"] == 0
    assert [(e["kind"], e["amount"], e["note"]) for e in project["entries"]] == [
        ("estimate", 400_000, "Poles, fittings, cabling and labour."),
    ]
    assert project["entries"][0]["createdByName"] == "Panchayat Officer"


def test_a_proposal_needs_no_cost_and_refuses_a_nonsense_one(client, officer):
    assert _propose(client, officer, name="Cost not known yet")["finance"]["estimated"] is None
    refused = client.post(f"{API}/projects/proposals", headers=officer, json={
        "name": "Free streetlights", "description": "At no cost.", "ward": 9,
        "location": "Ward 9", "estimate": 0,
    })
    assert refused.status_code == 422


def test_linking_moves_the_complaints_on_and_tells_their_owners(
    client, officer, residents, two_complaints, proposal
):
    assert proposal["linkedGrievances"] == 2
    assert proposal["residentsAffected"] == 2

    mine = _grievance(client, residents["lata"], two_complaints[0]["id"])
    assert mine["status"] == "In Progress"
    assert mine["projectId"] == proposal["id"]
    assert [e["eventType"] for e in mine["events"]][-2:] == [
        "linked_to_project", "status_changed",
    ]
    # The resident follows the work from their own complaint.
    assert mine["project"]["stage"] == "proposed"
    assert mine["project"]["stageLabel"] == "Proposed"
    assert mine["project"]["linkedGrievances"] == 2


def test_complaints_are_linked_not_merged(client, officer, two_complaints, proposal):
    """Each resident keeps their own complaint, with their own words."""
    titles = {_grievance(client, officer, g["id"])["title"] for g in two_complaints}
    assert titles == {g["title"] for g in two_complaints}


def test_a_complaint_answers_to_one_work_at_a_time(client, officer, two_complaints, proposal):
    resp = client.post(f"{API}/projects/proposals", headers=officer, json={
        "name": "A second proposal for the same thing", "description": "Duplicate.",
        "ward": 9, "location": "Ward 9", "grievanceIds": [two_complaints[0]["id"]],
    })
    assert resp.status_code == 409
    # And the refused proposal left nothing behind.
    names = [p["name"] for p in client.get(f"{API}/projects", headers=officer).json()]
    assert "A second proposal for the same thing" not in names


def test_more_complaints_can_join_a_work_and_leave_it(client, officer, residents, proposal):
    late = _file(client, residents["priyanka"], "New streetlights wanted by the old well",
                 "Please install them.", ward=9)
    joined = _ok(client.post(
        f"{API}/projects/{proposal['id']}/grievances", headers=officer,
        json={"grievanceIds": [late["id"]]},
    ))
    assert joined["linkedGrievances"] == 3

    left = _ok(client.delete(
        f"{API}/projects/{proposal['id']}/grievances/{late['id']}", headers=officer,
    ))
    assert left["linkedGrievances"] == 2
    assert _grievance(client, officer, late["id"])["projectId"] is None


def test_an_officer_sees_who_asked_and_a_resident_sees_how_many(
    client, officer, residents, proposal
):
    for_officer = _project(client, officer, proposal["id"])
    assert {g["citizenName"] for g in for_officer["grievances"]} == {
        "Lata Shinde", "Walk-in complainant",
    }

    for_resident = _project(client, residents["priyanka"], proposal["id"])
    assert for_resident["grievances"] == []
    assert for_resident["linkedGrievances"] == 2
    assert "Lata" not in str(for_resident)


def test_the_vocabulary_is_served_not_mistaken_for_a_project(client, residents):
    body = _ok(client.get(f"{API}/projects/vocabulary", headers=residents["lata"]))
    assert [s["code"] for s in body["stages"]] == works.STAGES
    assert {s["code"] for s in body["fundingSources"]} == set(works.FUNDING_SOURCES)
    assert {k["code"] for k in body["entryKinds"]} == set(works.ENTRY_KINDS)
    assert all(item["labelMr"] for item in body["assetTypes"])


# ─────────────────────────────────────────────────────────────────────────────
# The stages
# ─────────────────────────────────────────────────────────────────────────────

def test_the_screen_is_told_what_may_be_done_next(client, officer, proposal):
    """The stage rules live in one place. The frontend offers what it is sent."""
    assert proposal["steps"] == {
        "actions": ["verify", "reject", "hold"],
        "entryKinds": ["estimate"],
        "canRecordProgress": False,
    }
    started = _walk_to(client, officer, proposal["id"], "in_progress")
    assert started["steps"] == {
        "actions": ["complete", "hold"],
        "entryKinds": ["estimate", "approved", "spent"],
        "canRecordProgress": True,
    }


def test_the_screen_is_not_offered_a_step_that_could_only_be_refused(client, officer, proposal):
    """Once the whole sanction has arrived there is nothing left to receive,
    and nothing can be paid from an empty balance."""
    pid = proposal["id"]
    _ok(_decide(client, officer, pid, "verify", "Checked."))
    _ok(_decide(client, officer, pid, "approve"))
    _ok(_entry(client, officer, pid, "requested", 100_000))
    _ok(_entry(client, officer, pid, "approved", 100_000))

    part = _ok(_entry(client, officer, pid, "received", 60_000))
    assert "received" in part["steps"]["entryKinds"]          # 40,000 still to come
    full = _ok(_entry(client, officer, pid, "received", 40_000))
    assert "received" not in full["steps"]["entryKinds"]

    _ok(_decide(client, officer, pid, "start"))
    assert "spent" in _project(client, officer, pid)["steps"]["entryKinds"]
    emptied = _ok(_entry(client, officer, pid, "spent", 100_000))
    assert "spent" not in emptied["steps"]["entryKinds"]

    # A larger sanction reopens both.
    raised = _ok(_entry(client, officer, pid, "approved", 150_000))
    assert "received" in raised["steps"]["entryKinds"]


@pytest.mark.parametrize("action", ["approve", "start", "complete", "resume"])
def test_a_decision_out_of_turn_is_refused(client, officer, proposal, action):
    resp = _decide(client, officer, proposal["id"], action)
    assert resp.status_code == 409
    assert "Proposed" in resp.json()["detail"]
    assert _project(client, officer, proposal["id"])["stage"] == "proposed"


@pytest.mark.parametrize("kind", ["requested", "approved", "received", "spent"])
def test_money_cannot_be_recorded_before_its_stage(client, officer, proposal, kind):
    resp = _entry(client, officer, proposal["id"], kind, 50_000)
    assert resp.status_code == 409
    assert _project(client, officer, proposal["id"])["entries"] == []


@pytest.mark.parametrize("action", ["verify", "reject", "hold"])
def test_the_decisions_that_need_a_reason_are_refused_without_one(
    client, officer, proposal, action
):
    for empty in (None, "", "   "):
        assert _decide(client, officer, proposal["id"], action, empty).status_code == 400
    assert _project(client, officer, proposal["id"])["stage"] == "proposed"


def test_recording_the_money_is_what_moves_the_stage(client, officer, proposal):
    """There is no "mark budget requested" button. Entering the amount
    requested is the step, so the two cannot disagree."""
    pid = proposal["id"]
    _ok(_decide(client, officer, pid, "verify", "Five poles are needed."))
    _ok(_decide(client, officer, pid, "approve", "Approved by the Panchayat."))

    assert _ok(_entry(client, officer, pid, "requested", 120_000))["stage"] == "budget_requested"
    assert _ok(_entry(client, officer, pid, "approved", 120_000))["stage"] == "budget_approved"
    assert _ok(_entry(client, officer, pid, "received", 120_000))["stage"] == "funds_received"

    # An estimate, by contrast, is information: it moves nothing.
    assert _ok(_entry(client, officer, pid, "estimate", 125_000))["stage"] == "funds_received"


def test_the_whole_life_of_a_work(client, officer, residents, two_complaints, proposal):
    pid = proposal["id"]

    verified = _ok(_decide(client, officer, pid, "verify", "Five poles are needed."))
    assert (verified["stage"], verified["status"]) == ("verified", "Planned")

    _ok(_entry(client, officer, pid, "estimate", 400_000, note="Poles, cable, labour."))

    meeting = client.get(f"{API}/sabha/meetings", headers=officer).json()[0]
    approved = _ok(_decide(client, officer, pid, "approve", "Approved in the Gram Sabha.",
                           sabhaMeetingId=meeting["id"]))
    assert approved["stage"] == "approved"
    assert approved["sabhaMeetingId"] == meeting["id"]
    assert approved["decisionNote"] == "Approved in the Gram Sabha."

    _ok(_entry(client, officer, pid, "requested", 400_000, fundingSource="cfc"))
    sanctioned = _ok(_entry(client, officer, pid, "approved", 350_000, fundingSource="cfc",
                            reference="PS/2026-27/212"))
    assert sanctioned["budget"] == 350_000
    assert sanctioned["fundingSource"] == "cfc"
    assert sanctioned["fundingSourceLabel"] == "Central Finance Commission grant"
    assert "partial_approval" in _flag_codes(sanctioned)

    funded = _ok(_entry(client, officer, pid, "received", 350_000))
    assert (funded["stage"], funded["status"]) == ("funds_received", "Planned")
    assert funded["finance"]["awaiting"] == 0

    started = _ok(_decide(client, officer, pid, "start"))
    assert (started["stage"], started["status"]) == ("in_progress", "Ongoing")
    assert started["startDate"] == date.today().isoformat()

    _ok(_entry(client, officer, pid, "spent", 160_000, reference="Bill 0147"))
    part = _ok(client.post(f"{API}/projects/{pid}/progress", headers=officer,
                           json={"unitsDone": 3}))
    assert (part["unitsDone"], part["physicalPercent"], part["progress"]) == (3, 60, 60)

    paid = _ok(_entry(client, officer, pid, "spent", 120_000))
    # The two figures every older screen reads are the ledger's totals.
    assert (paid["budget"], paid["utilized"]) == (350_000, 280_000)
    assert paid["finance"] == {
        "estimated": 400_000, "requested": 400_000, "approved": 350_000,
        "received": 350_000, "spent": 280_000, "awaiting": 0, "balance": 70_000,
        "remaining": 70_000, "financialPercent": 80,
    }

    _ok(client.post(f"{API}/projects/{pid}/progress", headers=officer, json={"unitsDone": 5}))
    done = _ok(_decide(client, officer, pid, "complete"))
    assert (done["stage"], done["status"], done["progress"]) == ("completed", "Completed", 100)
    assert done["steps"]["actions"] == []

    # The history is the eight stages, in order, each with who and why.
    moves = [e["toStage"] for e in done["events"] if e["eventType"] in ("proposed", "stage_changed")]
    assert moves == works.STAGES
    assert {e["actorName"] for e in done["events"]} == {"Panchayat Officer"}

    # What it built is in the asset register, once, as a count.
    built = [f for f in client.get(f"{API}/facilities", headers=officer).json()
             if f["projectId"] == pid]
    assert len(built) == 1
    assert built[0]["facilityType"] == "streetlight"
    assert built[0]["quantity"] == 5
    assert built[0]["installedOn"] == date.today().isoformat()

    # And the people who asked are told, and asked whether it is true.
    mine = _grievance(client, residents["lata"], two_complaints[0]["id"])
    assert mine["status"] == "Resolved"
    assert mine["citizenFeedback"] is None
    assert "Please confirm" in mine["events"][-1]["note"]
    assert mine["project"]["stage"] == "completed"


def test_completing_twice_registers_the_asset_once(client, officer, proposal):
    pid = proposal["id"]
    _walk_to(client, officer, pid, "in_progress")
    _ok(client.post(f"{API}/projects/{pid}/progress", headers=officer, json={"unitsDone": 5}))
    _ok(_decide(client, officer, pid, "complete"))
    assert _decide(client, officer, pid, "complete").status_code == 409

    with SessionLocal() as db:
        assert len(list(db.scalars(select(Facility).where(Facility.project_id == pid)))) == 1


def test_a_work_is_not_complete_until_the_count_is_reached(client, officer, proposal):
    pid = proposal["id"]
    _walk_to(client, officer, pid, "in_progress")
    _ok(client.post(f"{API}/projects/{pid}/progress", headers=officer, json={"unitsDone": 3}))

    resp = _decide(client, officer, pid, "complete")
    assert resp.status_code == 400
    assert "3 of 5 streetlights" in resp.json()["detail"]

    # Either finish the rest, or say the plan changed — on the record.
    revised = _ok(client.patch(f"{API}/projects/{pid}", headers=officer, json={"unitsPlanned": 3}))
    assert (revised["unitsPlanned"], revised["physicalPercent"]) == (3, 100)
    assert _ok(_decide(client, officer, pid, "complete"))["stage"] == "completed"
    notes = [e["note"] for e in _project(client, officer, pid)["events"]]
    assert "Planned number revised from 5 to 3." in notes


def test_progress_is_a_count_where_the_work_has_one(client, officer, proposal):
    pid = proposal["id"]
    url = f"{API}/projects/{pid}/progress"
    # Not before the work has started.
    assert client.post(url, headers=officer, json={"unitsDone": 1}).status_code == 409

    _walk_to(client, officer, pid, "in_progress")
    assert client.post(url, headers=officer, json={"progress": 50}).status_code == 400
    assert client.post(url, headers=officer, json={"unitsDone": 6}).status_code == 400
    assert client.patch(f"{API}/projects/{pid}", headers=officer,
                        json={"progress": 50}).status_code == 400
    assert _ok(client.post(url, headers=officer, json={"unitsDone": 2}))["physicalPercent"] == 40


def test_a_work_with_no_count_is_recorded_as_a_percentage(client, officer):
    project = _propose(client, officer, name="Repainting the Panchayat office")
    pid = project["id"]
    _walk_to(client, officer, pid, "in_progress")
    half = _ok(client.post(f"{API}/projects/{pid}/progress", headers=officer,
                           json={"progress": 50}))
    assert (half["progress"], half["physicalPercent"]) == (50, 50)
    # Reaching 100% is finishing, so it goes through the same door.
    done = _ok(client.patch(f"{API}/projects/{pid}", headers=officer, json={"progress": 100}))
    assert (done["stage"], done["status"]) == ("completed", "Completed")
    # Nothing was said to have been built, so nothing joins the register.
    with SessionLocal() as db:
        assert db.scalar(select(Facility.id).where(Facility.project_id == pid)) is None


def test_delayed_is_something_only_a_work_in_progress_can_be(client, officer, proposal):
    pid = proposal["id"]
    early = client.patch(f"{API}/projects/{pid}", headers=officer, json={"status": "Delayed"})
    assert early.status_code == 409

    _walk_to(client, officer, pid, "in_progress")
    late = _ok(client.patch(f"{API}/projects/{pid}", headers=officer, json={"status": "Delayed"}))
    assert (late["status"], late["statusMr"], late["stage"]) == (
        "Delayed", "विलंब झालेला", "in_progress",
    )


# ─────────────────────────────────────────────────────────────────────────────
# Rejecting and holding
# ─────────────────────────────────────────────────────────────────────────────

def test_a_rejected_proposal_tells_the_residents_why_and_leaves_their_complaints_open(
    client, officer, residents, two_complaints, proposal
):
    reason = "The stretch is private land; the Panchayat cannot light it."
    rejected = _ok(_decide(client, officer, proposal["id"], "reject", reason))
    assert (rejected["stage"], rejected["status"]) == ("rejected", "Rejected")
    assert rejected["stageIndex"] is None
    assert rejected["decisionNote"] == reason
    assert rejected["steps"] == {"actions": [], "entryKinds": [], "canRecordProgress": False}

    mine = _grievance(client, residents["lata"], two_complaints[0]["id"])
    assert reason in mine["events"][-1]["note"]
    assert mine["project"]["decisionNote"] == reason
    # Refusing one answer to a problem is not the problem going away.
    assert mine["status"] == "In Progress"


def test_a_work_whose_money_has_arrived_is_held_not_rejected(client, officer, proposal):
    pid = proposal["id"]
    _walk_to(client, officer, pid, "funds_received")

    refused = _decide(client, officer, pid, "reject", "Changed our minds.")
    assert refused.status_code == 409

    held = _ok(_decide(client, officer, pid, "hold", "Pole supplier has not delivered."))
    assert (held["stage"], held["status"], held["statusMr"]) == ("on_hold", "On Hold", "स्थगित")
    assert held["steps"]["actions"] == ["resume"]

    # Nothing is paid or received on a held work.
    assert _entry(client, officer, pid, "spent", 1_000).status_code == 409
    assert _decide(client, officer, pid, "start").status_code == 409

    resumed = _ok(_decide(client, officer, pid, "resume"))
    assert (resumed["stage"], resumed["status"]) == ("funds_received", "Planned")
    assert _ok(_decide(client, officer, pid, "start"))["stage"] == "in_progress"


# ─────────────────────────────────────────────────────────────────────────────
# The ledger
# ─────────────────────────────────────────────────────────────────────────────

def test_money_cannot_get_ahead_of_itself(client, officer, proposal):
    pid = proposal["id"]
    _ok(_decide(client, officer, pid, "verify", "Checked."))
    _ok(_decide(client, officer, pid, "approve"))
    _ok(_entry(client, officer, pid, "requested", 300_000))
    _ok(_entry(client, officer, pid, "approved", 300_000))

    over = _entry(client, officer, pid, "received", 350_000)
    assert over.status_code == 400
    assert "₹3,00,000 approved" in over.json()["detail"]

    # An instalment is fine, and so is the next one — up to the sanction.
    _ok(_entry(client, officer, pid, "received", 200_000))
    assert _entry(client, officer, pid, "received", 150_000).status_code == 400

    _ok(_decide(client, officer, pid, "start"))
    overspent = _entry(client, officer, pid, "spent", 250_000)
    assert overspent.status_code == 400
    assert "₹2,00,000 received" in overspent.json()["detail"]
    _ok(_entry(client, officer, pid, "spent", 150_000))

    # The sanction cannot be revised to less than has already come in.
    cut = _entry(client, officer, pid, "approved", 150_000)
    assert cut.status_code == 400
    assert "₹2,00,000 has already been received" in cut.json()["detail"]

    project = _project(client, officer, pid)
    assert project["finance"]["received"] == 200_000
    assert project["finance"]["spent"] == 150_000
    assert project["finance"]["awaiting"] == 100_000
    assert "funds_awaited" in _flag_codes(project)


def test_an_entry_has_to_be_a_real_amount_on_a_real_day(client, officer, proposal):
    pid = proposal["id"]
    assert _entry(client, officer, pid, "estimate", 0).status_code == 422
    assert _entry(client, officer, pid, "estimate", -5).status_code == 422
    assert _entry(client, officer, pid, "bribe", 100).status_code == 422
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    assert _entry(client, officer, pid, "estimate", 100, entryDate=tomorrow).status_code == 400
    assert _entry(client, officer, pid, "estimate", 100, fundingSource="lottery").status_code == 400
    assert _project(client, officer, pid)["entries"] == []


def test_a_revision_is_a_new_entry_and_the_earlier_figure_stays(client, officer, proposal):
    pid = proposal["id"]
    _ok(_entry(client, officer, pid, "estimate", 400_000))
    assert "estimate_up" not in _flag_codes(_project(client, officer, pid))

    revised = _ok(_entry(client, officer, pid, "estimate", 500_000, note="Cable rerouted."))
    assert revised["finance"]["estimated"] == 500_000
    assert [e["amount"] for e in revised["entries"]] == [400_000, 500_000]

    flag = next(f for f in revised["flags"] if f["code"] == "estimate_up")
    assert "₹4,00,000 to ₹5,00,000 (+25%)" in flag["message"]


def test_there_is_no_way_to_edit_or_delete_an_entry(client, officer, proposal):
    pid = proposal["id"]
    entry = _ok(_entry(client, officer, pid, "estimate", 400_000))["entries"][0]
    url = f"{API}/projects/{pid}/budget-entries/{entry['id']}"
    for method in ("patch", "put", "delete"):
        assert getattr(client, method)(url, headers=officer).status_code in (404, 405)


def test_filling_in_an_earlier_approval_does_not_overwrite_the_current_one(
    client, officer, proposal
):
    """The date decides which figure stands, not the order of typing."""
    pid = proposal["id"]
    _walk_to(client, officer, pid, "budget_requested", amount=500_000)
    _ok(_entry(client, officer, pid, "approved", 300_000))

    last_month = (date.today() - timedelta(days=30)).isoformat()
    backfilled = _ok(_entry(client, officer, pid, "approved", 400_000, entryDate=last_month,
                            note="First sanction, later reduced."))
    assert backfilled["finance"]["approved"] == 300_000
    assert backfilled["budget"] == 300_000
    # Shown in date order, so the figure that stands is the last one listed.
    assert [e["amount"] for e in backfilled["entries"] if e["kind"] == "approved"] == [
        400_000, 300_000,
    ]


def test_a_same_day_correction_replaces_the_figure(client, officer, proposal):
    pid = proposal["id"]
    _walk_to(client, officer, pid, "budget_requested", amount=500_000)
    _ok(_entry(client, officer, pid, "approved", 300_000))
    corrected = _ok(_entry(client, officer, pid, "approved", 330_000, note="Typed wrongly."))
    assert corrected["finance"]["approved"] == 330_000


def test_the_old_way_of_registering_a_work_opens_a_ledger_for_it(client, officer):
    created = _ok(client.post(f"{API}/projects", headers=officer, json={
        "name": "Community hall roof", "nameMr": "समाज मंदिर छत",
        "description": "Already under way.", "descriptionMr": "सुरू आहे.",
        "progress": 40, "budget": 800_000, "utilized": 300_000,
        "status": "Ongoing", "statusMr": "सुरू असलेले", "ward": 9,
        "location": "Ward 9", "locationMr": "प्रभाग ९",
        "latitude": 18.4884, "longitude": 74.0222,
    }))
    assert created["stage"] == "in_progress"
    assert created["finance"]["approved"] == created["finance"]["received"] == 800_000
    assert created["finance"]["spent"] == 300_000

    detail = _project(client, officer, created["id"])
    assert [(e["kind"], e["amount"]) for e in detail["entries"]] == [
        ("approved", 800_000), ("received", 800_000), ("spent", 300_000),
    ]
    # From here it is a work like any other.
    more = _ok(_entry(client, officer, created["id"], "spent", 100_000))
    assert more["utilized"] == 400_000


def test_a_work_can_be_registered_in_english_alone(client, officer):
    """This is exactly what the registration form sends when the officer leaves
    the Marathi boxes empty. It used to come back 422 with four missing fields,
    so the button on the screen could not have worked."""
    created = client.post(f"{API}/projects", headers=officer, json={
        "name": "Bus shelter at the chowk", "description": "", "progress": 0,
        "budget": 250_000, "utilized": 0, "status": "Ongoing", "ward": 9,
        "location": "Main chowk", "latitude": 18.4884, "longitude": 74.0222,
    })
    assert created.status_code == 201, created.text
    body = created.json()
    assert (body["nameMr"], body["locationMr"]) == ("Bus shelter at the chowk", "Main chowk")
    assert body["statusMr"] == "सुरू असलेले"


@pytest.mark.parametrize("project_id", ["proj_301", "proj_302", "proj_304"])
def test_the_seeded_works_have_a_ledger_that_adds_up_to_their_totals(
    client, officer, project_id
):
    project = _project(client, officer, project_id)
    assert project["finance"]["approved"] == project["budget"] > 0
    assert project["finance"]["spent"] == project["utilized"]
    opening = [e for e in project["entries"] if e["createdByName"] == "Carried over"]
    assert {e["kind"] for e in opening} == {"approved", "received", "spent"}
    assert {e["entryDate"] for e in opening} == {"2026-04-01"}
    assert project["financialYear"] is not None


# ─────────────────────────────────────────────────────────────────────────────
# Putting a wrong entry right
# ─────────────────────────────────────────────────────────────────────────────

def _correct(client, headers, project_id: str, entry_id: str, amount: float,
             reason: str = "Typed wrongly."):
    return client.post(
        f"{API}/projects/{project_id}/budget-entries/{entry_id}/corrections",
        headers=headers, json={"amount": amount, "reason": reason},
    )


def _entries(project: dict, kind: str) -> list[dict]:
    """The entries of one kind as first recorded, leaving out correcting lines."""
    return [e for e in project["entries"] if e["kind"] == kind and not e["correctsId"]]


@pytest.fixture
def paying(client, officer, proposal) -> dict:
    """A work in progress with 3,50,000 received and one payment of 1,60,000."""
    _walk_to(client, officer, proposal["id"], "in_progress", amount=350_000)
    return _ok(_entry(client, officer, proposal["id"], "spent", 160_000, reference="Bill 0147"))


def test_a_mistyped_payment_is_put_right_without_being_overwritten(client, officer, paying):
    """Payments add up, so a wrong one could not be fixed by typing another:
    1,60,000 entered where 16,000 was meant left "remaining" wrong for good."""
    pid = paying["id"]
    wrong = _entries(paying, "spent")[0]
    assert wrong["canCorrect"] is True
    assert wrong["correctedTo"] is None

    fixed = _ok(_correct(client, officer, pid, wrong["id"], 16_000, "One zero too many."))
    assert fixed["utilized"] == 16_000
    assert (fixed["finance"]["spent"], fixed["finance"]["balance"]) == (16_000, 334_000)

    # Nothing was overwritten: the first figure, the correction and the reason
    # are all still in the ledger.
    original = next(e for e in fixed["entries"] if e["id"] == wrong["id"])
    correction = next(e for e in fixed["entries"] if e["correctsId"] == wrong["id"])
    assert (original["amount"], original["correctedTo"]) == (160_000, 16_000)
    assert (correction["kind"], correction["amount"]) == ("spent", -144_000)
    assert correction["note"] == "One zero too many."
    assert correction["reference"] == "Bill 0147"
    assert correction["entryDate"] == original["entryDate"]
    assert correction["createdByName"] == "Panchayat Officer"
    assert correction["canCorrect"] is False

    notes = [e["note"] or "" for e in fixed["events"]]
    assert any("changed from ₹1,60,000 to ₹16,000 — One zero too many." in n for n in notes)


def test_an_entry_can_be_corrected_again_and_cancelled(client, officer, paying):
    pid = paying["id"]
    entry_id = _entries(paying, "spent")[0]["id"]

    _ok(_correct(client, officer, pid, entry_id, 16_000))
    # A second correction is to the entry, not to the first correction.
    again = _ok(_correct(client, officer, pid, entry_id, 18_000, "Bill was 18,000."))
    assert again["finance"]["spent"] == 18_000
    assert [e["amount"] for e in again["entries"] if e["correctsId"] == entry_id] == [
        -144_000, 2_000,
    ]
    assert next(e for e in again["entries"] if e["id"] == entry_id)["correctedTo"] == 18_000

    # Zero cancels a payment that should never have been recorded here.
    gone = _ok(_correct(client, officer, pid, entry_id, 0, "Belongs to another work."))
    assert (gone["finance"]["spent"], gone["utilized"]) == (0, 0)
    assert next(e for e in gone["entries"] if e["id"] == entry_id)["correctedTo"] == 0


def test_a_correction_needs_a_reason_and_a_different_amount(client, officer, paying):
    pid = paying["id"]
    entry_id = _entries(paying, "spent")[0]["id"]
    url = f"{API}/projects/{pid}/budget-entries/{entry_id}/corrections"

    assert client.post(url, headers=officer, json={"amount": 16_000}).status_code == 422
    assert client.post(url, headers=officer,
                       json={"amount": 16_000, "reason": ""}).status_code == 422
    assert _correct(client, officer, pid, entry_id, 16_000, "     ").status_code == 400
    assert _correct(client, officer, pid, entry_id, -5).status_code == 422

    unchanged = _correct(client, officer, pid, entry_id, 160_000)
    assert unchanged.status_code == 400
    assert "already stands at ₹1,60,000" in unchanged.json()["detail"]
    assert _project(client, officer, pid)["finance"]["spent"] == 160_000


def test_a_correction_cannot_break_the_rules_the_entries_obey(client, officer, paying):
    pid = paying["id"]
    spent_id = _entries(paying, "spent")[0]["id"]
    received_id = _entries(paying, "received")[0]["id"]

    # Spending still cannot exceed what was received...
    over = _correct(client, officer, pid, spent_id, 400_000)
    assert over.status_code == 400
    assert "more than the ₹3,50,000 received" in over.json()["detail"]

    # ...money received cannot drop below what has been spent...
    under = _correct(client, officer, pid, received_id, 100_000)
    assert under.status_code == 400
    assert "₹1,60,000 has already been spent" in under.json()["detail"]

    # ...or rise above what was approved.
    above = _correct(client, officer, pid, received_id, 500_000)
    assert above.status_code == 400
    assert "more than the ₹3,50,000 approved" in above.json()["detail"]

    project = _project(client, officer, pid)
    assert (project["finance"]["received"], project["finance"]["spent"]) == (350_000, 160_000)
    assert not [e for e in project["entries"] if e["correctsId"]]

    # Within the rules it goes through.
    lower = _ok(_correct(client, officer, pid, received_id, 200_000, "Second instalment not in yet."))
    assert (lower["finance"]["received"], lower["finance"]["awaiting"]) == (200_000, 150_000)


@pytest.mark.parametrize("kind", ["estimate", "requested", "approved"])
def test_a_figure_that_is_simply_replaced_is_not_corrected(client, officer, paying, kind):
    """The latest estimate, request or approval stands in place of the one
    before it, so there is nothing for a correction to do."""
    entry = _entries(paying, kind)[0] if _entries(paying, kind) else None
    if entry is None:
        entry = _entries(_ok(_entry(client, officer, paying["id"], kind, 350_000)), kind)[0]
    assert entry["canCorrect"] is False
    resp = _correct(client, officer, paying["id"], entry["id"], 1)
    assert resp.status_code == 400
    assert "record the right figure as a new entry" in resp.json()["detail"]


def test_a_correcting_line_is_not_itself_corrected(client, officer, paying):
    pid = paying["id"]
    entry_id = _entries(paying, "spent")[0]["id"]
    fixed = _ok(_correct(client, officer, pid, entry_id, 16_000))
    correction = next(e for e in fixed["entries"] if e["correctsId"] == entry_id)
    resp = _correct(client, officer, pid, correction["id"], 5)
    assert resp.status_code == 400
    assert "Correct the entry it belongs to" in resp.json()["detail"]


def test_money_that_never_arrived_takes_the_work_back_a_stage(client, officer, proposal):
    """Funds were recorded as received by mistake. Cancelling the entry means
    the work is not at "Funds received" after all, and it cannot be started."""
    pid = proposal["id"]
    funded = _walk_to(client, officer, pid, "funds_received", amount=200_000)
    received_id = _entries(funded, "received")[0]["id"]

    undone = _ok(_correct(client, officer, pid, received_id, 0, "Credited to another scheme."))
    assert (undone["stage"], undone["finance"]["received"]) == ("budget_approved", 0)
    assert _decide(client, officer, pid, "start").status_code == 409
    assert "received" in undone["steps"]["entryKinds"]

    # Once the work has started the funds cannot be corrected to nothing.
    _ok(_entry(client, officer, pid, "received", 200_000))
    _ok(_decide(client, officer, pid, "start"))
    started = _project(client, officer, pid)
    live = next(e for e in _entries(started, "received") if e["correctedTo"] is None)
    resp = _correct(client, officer, pid, live["id"], 0, "Did not arrive.")
    assert resp.status_code == 400
    assert "put the work on hold" in resp.json()["detail"]


def test_nothing_is_corrected_on_a_held_work(client, officer, paying):
    pid = paying["id"]
    entry_id = _entries(paying, "spent")[0]["id"]
    held = _ok(_decide(client, officer, pid, "hold", "Dispute with the supplier."))
    assert not any(e["canCorrect"] for e in held["entries"])
    assert _correct(client, officer, pid, entry_id, 16_000).status_code == 409


def test_a_correction_shows_in_the_year_the_entry_was_dated(client, officer):
    """A payment dated last year and corrected today is right in last year's
    figures — not wrong there and reversed in this year's."""
    project = _propose(client, officer, name="Cattle trough at the weekly market")
    pid = project["id"]
    with clock.at(date(2023, 2, 10)):                      # FY 2022-23
        _walk_to(client, officer, pid, "in_progress", amount=90_000)
        paid = _ok(_entry(client, officer, pid, "spent", 80_000))

    _ok(_correct(client, officer, pid, _entries(paid, "spent")[0]["id"], 8_000))

    then = _overview(client, officer, fy="2022-23")
    assert next(r for r in then["projects"] if r["id"] == pid)["spent"] == 8_000
    now = _overview(client, officer, fy=works.financial_year(date.today()))
    assert pid not in [r["id"] for r in now["projects"]]


def test_an_opening_balance_can_be_corrected_too(client, officer):
    created = _ok(client.post(f"{API}/projects", headers=officer, json={
        "name": "Well deepening", "progress": 30, "budget": 500_000, "utilized": 250_000,
        "status": "Ongoing", "ward": 9, "location": "Ward 9",
        "latitude": 18.4884, "longitude": 74.0222,
    }))
    detail = _project(client, officer, created["id"])
    spent = _entries(detail, "spent")[0]
    assert spent["note"] == "Opening balance carried over from the project record."
    assert spent["canCorrect"] is True
    fixed = _ok(_correct(client, officer, created["id"], spent["id"], 205_000,
                         "The old record included a bill that was never paid."))
    assert fixed["utilized"] == 205_000


def test_who_may_correct_an_entry(client, officer, neighbour_officer, citizen, paying):
    pid = paying["id"]
    entry_id = _entries(paying, "spent")[0]["id"]
    assert _correct(client, citizen, pid, entry_id, 1).status_code == 403
    assert _correct(client, neighbour_officer, pid, entry_id, 1).status_code == 403
    assert _correct(client, officer, pid, "bud_does_not_exist", 1).status_code == 404

    # An entry cannot be reached through another work either.
    other = _propose(client, officer, name="Another work entirely")
    assert _correct(client, officer, other["id"], entry_id, 1).status_code == 404
    assert _project(client, officer, pid)["finance"]["spent"] == 160_000


# ─────────────────────────────────────────────────────────────────────────────
# What looks wrong
# ─────────────────────────────────────────────────────────────────────────────

def test_spending_far_ahead_of_the_work_is_flagged(client, officer, proposal):
    pid = proposal["id"]
    _walk_to(client, officer, pid, "in_progress")

    _ok(_entry(client, officer, pid, "spent", 40_000))
    _ok(client.post(f"{API}/projects/{pid}/progress", headers=officer, json={"unitsDone": 1}))
    # 40% spent, 20% built: twenty points apart, under the line.
    assert "spend_ahead" not in _flag_codes(_project(client, officer, pid))

    flagged = _ok(_entry(client, officer, pid, "spent", 10_000))
    flag = next(f for f in flagged["flags"] if f["code"] == "spend_ahead")
    assert flag["severity"] == "warning"
    assert "50% of the approved budget has been spent with 20% of the work recorded" in flag["message"]
    assert flag["messageMr"]

    # Catching up clears it. The flag is a comparison, not a mark against the work.
    caught_up = _ok(client.post(f"{API}/projects/{pid}/progress", headers=officer,
                                json={"unitsDone": 3}))
    assert "spend_ahead" not in _flag_codes(caught_up)


def test_a_proposal_left_waiting_for_its_budget_is_flagged(client, officer, proposal):
    pid = proposal["id"]
    with clock.at(date.today() - timedelta(days=61)):
        _walk_to(client, officer, pid, "budget_requested")

    waiting = _project(client, officer, pid)
    assert waiting["daysInStage"] == 61
    flag = next(f for f in waiting["flags"] if f["code"] == "stalled")
    assert flag["message"] == "At “Budget requested” for 61 days."

    # The answer arriving is what clears it.
    assert "stalled" not in _flag_codes(_ok(_entry(client, officer, pid, "approved", 100_000)))


def test_sixty_days_is_still_within_the_time_allowed(client, officer, proposal):
    with clock.at(date.today() - timedelta(days=60)):
        _walk_to(client, officer, proposal["id"], "budget_requested")
    assert "stalled" not in _flag_codes(_project(client, officer, proposal["id"]))


def test_a_work_past_its_expected_date_is_flagged_until_it_is_done(client, officer):
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    project = _propose(client, officer, name="Culvert repair", expectedCompletion=yesterday)
    assert "overdue" in _flag_codes(project)

    _walk_to(client, officer, project["id"], "in_progress")
    done = _ok(_decide(client, officer, project["id"], "complete"))
    assert done["flags"] == []


def test_a_healthy_work_has_no_flags(client, officer, proposal):
    assert _walk_to(client, officer, proposal["id"], "in_progress")["flags"] == []


# ─────────────────────────────────────────────────────────────────────────────
# The resident's answer
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def finished(client, officer, residents) -> tuple[dict, dict]:
    """A work completed for one resident's complaint: (complaint, project)."""
    complaint = _file(client, residents["sanjay"], "Need 2 new streetlights at the tank",
                      "Please install them.", ward=9)
    project = _propose(client, officer, [complaint["id"]], unitsPlanned=2,
                       unitLabel="streetlights", assetType="streetlight")
    _walk_to(client, officer, project["id"], "in_progress")
    _ok(client.post(f"{API}/projects/{project['id']}/progress", headers=officer,
                    json={"unitsDone": 2}))
    _ok(_decide(client, officer, project["id"], "complete"))
    return complaint, project


def _feedback(client, headers, grievance_id: str, resolved: bool, note: str | None = None):
    return client.post(f"{API}/grievances/{grievance_id}/feedback", headers=headers,
                       json={"resolved": resolved, "note": note})


def test_only_the_resident_who_asked_gets_to_answer(client, officer, residents, finished):
    complaint, _ = finished
    assert _feedback(client, officer, complaint["id"], True).status_code == 403
    assert _feedback(client, residents["lata"], complaint["id"], True).status_code == 403
    assert _grievance(client, officer, complaint["id"])["citizenFeedback"] is None


def test_there_is_nothing_to_confirm_until_the_office_says_it_is_done(client, residents):
    pending = _file(client, residents["sanjay"], "Streetlight broken at the tank",
                    "Since last night.", ward=9)
    assert _feedback(client, residents["sanjay"], pending["id"], True).status_code == 409


def test_confirming_closes_the_loop(client, officer, residents, finished):
    complaint, project = finished
    body = _ok(_feedback(client, residents["sanjay"], complaint["id"], True, "Both are lit."))
    assert body["citizenFeedback"] == "confirmed"
    assert body["status"] == "Resolved"
    assert body["events"][-1]["eventType"] == "confirmed"
    assert body["events"][-1]["actorName"] == "Sanjay Patil"

    # Once is enough.
    assert _feedback(client, residents["sanjay"], complaint["id"], True).status_code == 409
    assert "reopened" not in _flag_codes(_project(client, officer, project["id"]))


def test_saying_no_reopens_the_complaint_and_flags_the_work(
    client, officer, residents, finished
):
    complaint, project = finished
    # "No" on its own gives the office nothing to look at.
    assert _feedback(client, residents["sanjay"], complaint["id"], False).status_code == 400

    body = _ok(_feedback(client, residents["sanjay"], complaint["id"], False,
                         "Only one of the two works."))
    assert (body["status"], body["citizenFeedback"]) == ("In Progress", "reopened")
    assert body["resolvedDate"] is None
    assert body["events"][-1]["eventType"] == "reopened"
    assert "Only one of the two works." in body["events"][-1]["note"]

    work = _project(client, officer, project["id"])
    flag = next(f for f in work["flags"] if f["code"] == "reopened")
    assert "1 resident(s) say this work is not done" in flag["message"]
    assert work["grievances"][0]["feedbackNote"] == "Only one of the two works."

    # The office fixes it and resolves again; the question is put afresh.
    again = _ok(client.patch(f"{API}/grievances/{complaint['id']}", headers=officer,
                             json={"status": "Resolved", "officerNotes": "Second light fixed."}))
    assert again["citizenFeedback"] is None
    assert "reopened" not in _flag_codes(_project(client, officer, project["id"]))
    assert _ok(_feedback(client, residents["sanjay"], complaint["id"], True))["citizenFeedback"] == "confirmed"


def test_an_ordinary_repair_gets_the_same_question(client, officer, residents):
    """Feedback is for every complaint, not only the ones that became works."""
    repair = _file(client, residents["sanjay"], "Streetlight broken at the gate",
                   "It flickers.", ward=9)
    _ok(client.patch(f"{API}/grievances/{repair['id']}", headers=officer,
                     json={"status": "Resolved"}))
    assert _ok(_feedback(client, residents["sanjay"], repair["id"], True))["citizenFeedback"] == "confirmed"


# ─────────────────────────────────────────────────────────────────────────────
# The budget across all works
# ─────────────────────────────────────────────────────────────────────────────

def _overview(client, headers, **params) -> dict:
    return _ok(client.get(f"{API}/budget/overview", headers=headers, params=params))


def test_the_overview_is_the_sum_of_the_ledgers(client, officer):
    projects = client.get(f"{API}/projects", headers=officer).json()
    counted = [p for p in projects if p["stage"] != "rejected"]
    overview = _overview(client, officer)

    assert len(overview["projects"]) == len(projects)
    totals = overview["totals"]
    for field in ("approved", "received", "spent", "balance", "awaiting", "remaining"):
        expected = sum(p["finance"][field] or 0 for p in counted)
        assert totals[field] == pytest.approx(expected), field
    assert totals["balance"] == pytest.approx(totals["received"] - totals["spent"])
    assert totals["remaining"] == pytest.approx(totals["balance"] + totals["awaiting"])
    assert sum(overview["stageCounts"].values()) == len(projects)


def test_each_step_of_a_work_moves_the_right_total(client, officer, proposal):
    pid = proposal["id"]

    def totals() -> dict:
        # The amounts; the percentage is derived from them and moves with all.
        money = _overview(client, officer)["totals"]
        return {k: v for k, v in money.items() if k != "utilisationPercent"}

    def moved(before: dict) -> dict:
        after = totals()
        return {k: round(after[k] - before[k]) for k in before if round(after[k] - before[k])}

    start = totals()
    _ok(_decide(client, officer, pid, "verify", "Checked."))
    _ok(_entry(client, officer, pid, "estimate", 400_000))
    assert moved(start) == {"estimated": 400_000}

    _ok(_decide(client, officer, pid, "approve"))
    _ok(_entry(client, officer, pid, "requested", 400_000))
    assert moved(start) == {"estimated": 400_000, "requestedPending": 400_000}

    # Once it is decided it is no longer pending, whatever the answer was.
    _ok(_entry(client, officer, pid, "approved", 350_000))
    assert moved(start) == {"estimated": 400_000, "approved": 350_000,
                            "awaiting": 350_000, "remaining": 350_000}

    # Remaining is what is approved and not yet paid out: it does not move when
    # the money arrives, only when it is spent.
    _ok(_entry(client, officer, pid, "received", 350_000))
    assert moved(start) == {"estimated": 400_000, "approved": 350_000,
                            "received": 350_000, "balance": 350_000, "remaining": 350_000}

    _ok(_decide(client, officer, pid, "start"))
    _ok(_entry(client, officer, pid, "spent", 280_000))
    assert moved(start) == {"estimated": 400_000, "approved": 350_000,
                            "received": 350_000, "spent": 280_000,
                            "balance": 70_000, "remaining": 70_000}


def test_each_budget_row_says_what_can_be_recorded_next(client, officer, citizen, proposal):
    """The budget screen offers an officer the next entry for each work. It is
    sent with the row, so the screen holds no copy of the stage rules."""
    pid = proposal["id"]

    def row(headers=officer) -> dict:
        return next(r for r in _overview(client, headers)["projects"] if r["id"] == pid)

    assert row()["steps"]["entryKinds"] == ["estimate"]
    _walk_to(client, officer, pid, "approved")
    assert row()["steps"]["entryKinds"] == ["estimate", "requested"]
    _ok(_entry(client, officer, pid, "requested", 100_000))
    _ok(_entry(client, officer, pid, "approved", 100_000))
    assert "received" in row()["steps"]["entryKinds"]

    # It is the same whichever year is on screen...
    assert next(
        r for r in _overview(client, officer, fy=works.financial_year(date.today()))["projects"]
        if r["id"] == pid
    )["steps"] == row()["steps"]
    # ...and being told what could be recorded does not let a resident record it.
    assert row(citizen)["steps"] == row()["steps"]
    assert _entry(client, citizen, pid, "received", 100_000).status_code == 403


def test_a_rejected_proposal_is_listed_but_not_counted(client, officer, proposal):
    pid = proposal["id"]
    before = _overview(client, officer)["totals"]
    _ok(_entry(client, officer, pid, "estimate", 900_000))
    assert _overview(client, officer)["totals"]["estimated"] == before["estimated"] + 900_000

    _ok(_decide(client, officer, pid, "reject", "Not a Panchayat road."))
    after = _overview(client, officer)
    assert after["totals"] == before
    row = next(r for r in after["projects"] if r["id"] == pid)
    assert (row["stage"], row["estimated"]) == ("rejected", 900_000)


def test_money_is_totalled_by_where_it_came_from(client, officer, proposal):
    pid = proposal["id"]

    def source(code: str) -> dict:
        rows = _overview(client, officer)["sources"]
        return next((r for r in rows if r["code"] == code),
                    {"approved": 0, "received": 0, "spent": 0, "projects": 0})

    before = source("mla_mp")
    _ok(_decide(client, officer, pid, "verify", "Checked."))
    _ok(_decide(client, officer, pid, "approve"))
    _ok(_entry(client, officer, pid, "requested", 90_000, fundingSource="mla_mp"))
    _ok(_entry(client, officer, pid, "approved", 90_000, fundingSource="mla_mp"))
    _ok(_entry(client, officer, pid, "received", 60_000, fundingSource="mla_mp"))
    _ok(_decide(client, officer, pid, "start"))
    # A payment with no source given is paid from the work's own.
    _ok(_entry(client, officer, pid, "spent", 25_000))

    after = source("mla_mp")
    assert after["label"] == "MLA / MP local area fund"
    assert after["approved"] - before["approved"] == 90_000
    assert after["received"] - before["received"] == 60_000
    assert after["spent"] - before["spent"] == 25_000
    assert after["projects"] - before["projects"] == 1


def test_a_financial_year_counts_what_was_dated_in_it(client, officer):
    """A work sanctioned in one year and built in the next shows its approval
    in the first and its spending in the second."""
    project = _propose(client, officer, name="Anganwadi compound wall")
    pid = project["id"]
    with clock.at(date(2025, 3, 20)):                      # FY 2024-25
        _walk_to(client, officer, pid, "budget_approved", amount=600_000)
    with clock.at(date(2025, 4, 10)):                      # FY 2025-26
        _ok(_entry(client, officer, pid, "received", 600_000))
        _ok(_decide(client, officer, pid, "start"))
        _ok(_entry(client, officer, pid, "spent", 450_000))

    assert works.financial_year(date(2025, 3, 31)) == "2024-25"
    assert works.financial_year(date(2025, 4, 1)) == "2025-26"

    everything = _overview(client, officer)
    assert {"2024-25", "2025-26"} <= set(everything["financialYears"])
    assert everything["financialYear"] is None

    # Nothing else in the database is dated that far back, so each year's table
    # is this work alone.
    first = _overview(client, officer, fy="2024-25")
    assert [r["id"] for r in first["projects"]] == [pid]
    assert first["totals"]["approved"] == 600_000
    assert first["totals"]["received"] == first["totals"]["spent"] == 0

    second = _overview(client, officer, fy="2025-26")
    assert [r["id"] for r in second["projects"]] == [pid]
    assert second["totals"]["approved"] == 0
    assert (second["totals"]["received"], second["totals"]["spent"]) == (600_000, 450_000)

    assert pid not in [r["id"] for r in _overview(client, officer, fy="2026-27")["projects"]]


def test_a_financial_year_has_to_look_like_one(client, officer):
    resp = client.get(f"{API}/budget/overview", headers=officer, params={"fy": "last year"})
    assert resp.status_code == 400
    assert "2026-27" in resp.json()["detail"]


def test_a_resident_sees_the_same_budget_the_officer_does(client, officer, citizen):
    """What a Panchayat sanctioned, received and spent on public works is
    public, and there is nothing about any individual in it."""
    for_officer = _overview(client, officer)
    for_resident = _overview(client, citizen)
    assert for_resident["totals"] == for_officer["totals"]
    assert [r["id"] for r in for_resident["projects"]] == [r["id"] for r in for_officer["projects"]]


def test_the_budget_needs_a_login(client):
    assert client.get(f"{API}/budget/overview").status_code == 401


def test_the_dashboard_counts_a_proposal_as_planned_not_active(client, officer, proposal):
    def stats() -> dict:
        return client.get(f"{API}/analytics/dashboard", headers=officer).json()

    # `proposal` already exists, so start from a second one.
    before = stats()
    second = _propose(client, officer, name="A second proposal")
    planned = stats()
    assert planned["plannedProjects"] == before["plannedProjects"] + 1
    assert planned["activeProjects"] == before["activeProjects"]

    _walk_to(client, officer, second["id"], "budget_requested")
    assert stats()["budgetPendingProjects"] == before["budgetPendingProjects"] + 1

    _walk_to_in_progress = [
        _entry(client, officer, second["id"], "approved", 100_000),
        _entry(client, officer, second["id"], "received", 100_000),
        _decide(client, officer, second["id"], "start"),
    ]
    assert all(r.status_code in (200, 201) for r in _walk_to_in_progress)
    started = stats()
    assert started["plannedProjects"] == before["plannedProjects"]
    assert started["activeProjects"] == before["activeProjects"] + 1
    assert started["totalBudget"] == before["totalBudget"] + 100_000


# ─────────────────────────────────────────────────────────────────────────────
# Who may do what, and where
# ─────────────────────────────────────────────────────────────────────────────

def test_a_resident_cannot_drive_a_work(client, citizen, proposal):
    pid = proposal["id"]
    attempts = [
        client.post(f"{API}/projects/proposals", headers=citizen, json={
            "name": "A road to my house", "description": "Please.", "ward": 2,
            "location": "Ward 2",
        }),
        _decide(client, citizen, pid, "verify", "Looks fine to me."),
        _entry(client, citizen, pid, "estimate", 1),
        client.post(f"{API}/projects/{pid}/progress", headers=citizen, json={"progress": 100}),
        client.post(f"{API}/projects/{pid}/grievances", headers=citizen,
                    json={"grievanceIds": ["grv_201"]}),
        client.delete(f"{API}/projects/{pid}/grievances/grv_201", headers=citizen),
        client.patch(f"{API}/projects/{pid}", headers=citizen, json={"unitsPlanned": 1}),
        client.delete(f"{API}/projects/{pid}", headers=citizen),
    ]
    assert [r.status_code for r in attempts] == [403] * len(attempts)


def test_a_neighbouring_officer_cannot_touch_this_villages_work(
    client, neighbour_officer, officer, two_complaints, proposal
):
    pid = proposal["id"]
    gid = two_complaints[0]["id"]
    attempts = [
        client.get(f"{API}/projects/{pid}", headers=neighbour_officer),
        _decide(client, neighbour_officer, pid, "verify", "Checked from next door."),
        _decide(client, neighbour_officer, pid, "reject", "Not ours, but no."),
        _entry(client, neighbour_officer, pid, "estimate", 5),
        client.post(f"{API}/projects/{pid}/progress", headers=neighbour_officer,
                    json={"unitsDone": 1}),
        client.post(f"{API}/projects/{pid}/grievances", headers=neighbour_officer,
                    json={"grievanceIds": [gid]}),
        client.delete(f"{API}/projects/{pid}/grievances/{gid}", headers=neighbour_officer),
        client.get(f"{API}/grievances/{gid}/similar", headers=neighbour_officer),
    ]
    assert [r.status_code for r in attempts] == [403] * len(attempts)

    untouched = _project(client, officer, pid)
    assert (untouched["stage"], untouched["entries"], untouched["linkedGrievances"]) == (
        "proposed", [], 2,
    )


def test_a_neighbouring_officer_cannot_build_a_work_out_of_this_villages_complaints(
    client, neighbour_officer, officer, two_complaints
):
    gid = two_complaints[0]["id"]
    resp = client.post(f"{API}/projects/proposals", headers=neighbour_officer, json={
        "name": "Borrowed complaint", "description": "From next door.", "ward": 1,
        "location": "Theur", "grievanceIds": [gid],
    })
    assert resp.status_code == 403

    # Nor attach one to a work of their own.
    own = _propose(client, neighbour_officer, name="Theur bus shelter", ward=1,
                   location="Theur chowk")
    assert own["villageId"] == THEUR
    linked = client.post(f"{API}/projects/{own['id']}/grievances", headers=neighbour_officer,
                         json={"grievanceIds": [gid]})
    assert linked.status_code == 403
    assert _grievance(client, officer, gid)["projectId"] is None


def test_the_budget_of_one_village_is_not_shown_to_another(
    client, neighbour_officer, officer, admin
):
    home_ids = {r["id"] for r in _overview(client, officer)["projects"]}
    assert home_ids

    # Asking for it by name changes nothing: an officer's village is their own.
    for params in ({}, {"village_id": HOME}):
        theirs = _overview(client, neighbour_officer, **params)
        assert not home_ids & {r["id"] for r in theirs["projects"]}

    # An admin sees the block, and can narrow it.
    assert home_ids <= {r["id"] for r in _overview(client, admin)["projects"]}
    assert {r["id"] for r in _overview(client, admin, village_id=HOME)["projects"]} == home_ids
    assert not home_ids & {r["id"] for r in _overview(client, admin, village_id=THEUR)["projects"]}


def test_an_admin_has_to_say_which_village_a_proposal_is_for(client, admin):
    body = {"name": "District-level idea", "description": "No village.", "ward": 1,
            "location": "Somewhere"}
    assert client.post(f"{API}/projects/proposals", headers=admin, json=body).status_code == 400
    placed = _ok(client.post(f"{API}/projects/proposals", headers=admin,
                             json={**body, "villageId": THEUR}))
    assert placed["villageId"] == THEUR


def test_a_meeting_from_another_village_cannot_be_cited_as_the_decision(
    client, neighbour_officer, officer
):
    meeting = client.get(f"{API}/sabha/meetings", headers=officer).json()[0]
    theirs = _propose(client, neighbour_officer, name="Theur drain", ward=1,
                      location="Theur")
    _ok(_decide(client, neighbour_officer, theirs["id"], "verify", "Checked."))
    resp = _decide(client, neighbour_officer, theirs["id"], "approve", "Approved.",
                   sabhaMeetingId=meeting["id"])
    assert resp.status_code == 400
    assert _project(client, neighbour_officer, theirs["id"])["stage"] == "verified"


def test_deleting_a_work_frees_its_complaints_and_keeps_what_it_built(
    client, officer, finished
):
    complaint, project = finished
    assert client.delete(f"{API}/projects/{project['id']}", headers=officer).status_code == 204

    assert _grievance(client, officer, complaint["id"])["projectId"] is None
    with SessionLocal() as db:
        assert db.scalar(select(ProjectEvent.id).where(
            ProjectEvent.project_id == project["id"])) is None
        # The streetlights are still on their poles.
        orphan = db.scalar(select(Facility).where(Facility.quantity == 2,
                                                  Facility.facility_type == "streetlight",
                                                  Facility.project_id.is_(None)))
        assert orphan is not None


# ─────────────────────────────────────────────────────────────────────────────
# The audit trail
# ─────────────────────────────────────────────────────────────────────────────

def test_a_path_segment_that_is_not_an_id_is_not_recorded_as_a_record():
    assert audit.identify("/api/v1/projects/vocabulary") == (None, None)
    assert audit.identify("/api/v1/projects/proposals") == (None, None)
    assert audit.identify("/api/v1/grievances/classify") == (None, None)
    assert audit.identify("/api/v1/schemes/feed") == (None, None)
    # A real id still is.
    assert audit.identify("/api/v1/projects/proj_301/decisions") == ("project", "proj_301")
    assert audit.identify("/api/v1/projects/proj_301/budget-entries") == ("project", "proj_301")
    # A correction is filed under the work, not under the entry.
    assert audit.identify(
        "/api/v1/projects/proj_301/budget-entries/bud_1/corrections"
    ) == ("project", "proj_301")


def test_reference_reads_and_previews_stay_out_of_the_trail():
    record = audit._should_record
    assert record("GET", "/api/v1/projects/vocabulary", 200, None) is False
    assert record("POST", "/api/v1/grievances/classify", 200, None) is False
    # Opening a proposal changes something, so it is recorded — just not filed
    # under a project called "proposals".
    assert record("POST", "/api/v1/projects/proposals", 201, None) is True
    assert record("POST", "/api/v1/projects/proj_301/budget-entries", 201, "proj_301") is True


# ─────────────────────────────────────────────────────────────────────────────
# What the assistant is given
# ─────────────────────────────────────────────────────────────────────────────

def test_a_work_is_indexed_with_its_stage_and_money_and_never_with_names(
    client, officer, two_complaints, proposal
):
    pid = proposal["id"]
    _walk_to(client, officer, pid, "budget_requested", amount=400_000)
    _ok(_entry(client, officer, pid, "approved", 350_000))

    with SessionLocal() as db:
        drafts = {d.key: d for d in indexer.build_drafts(db)}

    work = drafts[f"project:{pid}"]
    assert "Stage: Budget approved" in work.content
    assert "₹3,50,000 has been approved against ₹4,00,000 requested" in work.content
    assert "raised by 2 resident(s) through 2 complaint(s)" in work.content
    assert "Lata" not in work.content and "Walk-in" not in work.content
    assert {"type": "grievance", "id": two_complaints[0]["id"],
            "label": "a complaint behind"} in work.links

    complaint = drafts[f"grievance:{two_complaints[0]['id']}"]
    assert "request for 5 for new work" in complaint.content
    assert f'"{proposal["name"]}"' in complaint.content
    assert complaint.links[0] == {"type": "project", "id": pid, "label": "the work answering"}


def test_a_proposal_with_no_estimate_is_not_indexed_as_a_budget_of_zero(client, officer):
    project = _propose(client, officer, name="Shade trees along the school road")
    with SessionLocal() as db:
        draft = next(d for d in indexer.build_drafts(db) if d.entity_id == project["id"])
    assert "No cost estimate has been recorded yet." in draft.content
    assert "₹0" not in draft.content


def test_the_assistant_can_say_which_works_are_waiting_and_why(client, officer, proposal):
    with clock.at(date.today() - timedelta(days=70)):
        _walk_to(client, officer, proposal["id"], "budget_requested")

    body = _ok(client.post(f"{API}/assistant/context", headers=officer,
                           json={"query": "which project proposals are stalled?"}))
    assert "projects" in body["topics"]
    assert "waiting for a budget decision" in " ".join(body["facts"])

    # The endpoint lists only a handful of works, and by now this run has made
    # dozens. Ask the retrieval layer for all of them to find this one.
    with SessionLocal() as db:
        user = db.get(User, "usr_officer")
        facts = retrieval.gather(db, "which project proposals are stalled?", user, HOME, limit=500).facts
    mine = next(f for f in facts if f.startswith(f"Project {proposal['id']}:"))
    assert "stage Budget requested" in mine
    assert "Worth checking: At “Budget requested” for 70 days." in mine
    assert "Lata" not in " ".join(facts)


def test_the_assistant_leads_with_the_works_that_need_looking_at(client, officer, proposal):
    """Only a few works fit in an answer. Listed by ward, a finished road came
    before a proposal that had been waiting three months."""
    with clock.at(date.today() - timedelta(days=90)):
        _walk_to(client, officer, proposal["id"], "budget_requested")

    with SessionLocal() as db:
        user = db.get(User, "usr_officer")
        facts = retrieval.gather(db, "how are the projects going?", user, HOME, limit=1).facts
    first = next(f for f in facts if f.startswith("Project "))
    assert "Worth checking:" in first


# ─────────────────────────────────────────────────────────────────────────────
# Small pieces
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("value, expected", [
    (0, "₹0"), (950, "₹950"), (1_000, "₹1,000"), (350_000, "₹3,50,000"),
    (12_345_678, "₹1,23,45,678"), (280_000.4, "₹2,80,000"), (-45_000, "-₹45,000"),
])
def test_rupees_are_grouped_the_way_they_are_written_here(value, expected):
    assert works.rupees(value) == expected


def test_the_clock_never_hands_out_the_same_moment_twice():
    """Several history rows are written per request and read back in time
    order. On a clock that ticks in milliseconds two of them could tie."""
    moments = [clock.now() for _ in range(500)]
    assert moments == sorted(set(moments))

    with clock.at(date(2026, 1, 15)):
        frozen = [clock.now() for _ in range(5)]
        assert clock.today() == date(2026, 1, 15)
    assert frozen == sorted(set(frozen))
    assert {m.date() for m in frozen} == {date(2026, 1, 15)}
    # And it is let go of afterwards.
    assert clock.today() == date.today()


def test_events_written_together_keep_the_order_they_were_written_in(
    client, officer, two_complaints, proposal
):
    with SessionLocal() as db:
        events = list(db.scalars(
            select(GrievanceEvent)
            .where(GrievanceEvent.grievance_id == two_complaints[1]["id"])
            .order_by(GrievanceEvent.created_at)
        ))
    # Linking and the move to In Progress are written in one request, a few
    # microseconds apart. (By this point in the run ward 9 has enough similar
    # complaints that filing also raises the priority; that entry is not what
    # is being checked.)
    kinds = [e.event_type for e in events if e.event_type != "priority_changed"]
    assert kinds == ["filed", "linked_to_project", "status_changed"]
    stamps = [e.created_at for e in events]
    assert len(set(stamps)) == len(stamps)


# ─────────────────────────────────────────────────────────────────────────────
# The demo
# ─────────────────────────────────────────────────────────────────────────────

def test_the_works_demo_is_built_by_the_real_rules_and_comes_out_again(client, officer, citizen):
    """The demo is not a set of rows written to look right. It is ten
    complaints filed and two works walked through the same rules as any other,
    with the clock set back — so if a rule changes, the demo changes with it,
    and if the demo breaks a rule, this fails."""
    today = date(2026, 10, 4)

    def counts() -> tuple[int, int, int]:
        with SessionLocal() as db:
            return tuple(len(list(db.scalars(select(m.id)))) for m in (Grievance, Project, Facility))

    before = counts()
    with SessionLocal() as db:
        seeder.seed_works_demo(db, today=today)
    try:
        assert counts() == (before[0] + 10, before[1] + 2, before[2])

        lights = _project(client, officer, "proj_demo_streetlights")
        assert (lights["stage"], lights["status"]) == ("in_progress", "Ongoing")
        assert (lights["unitsDone"], lights["unitsPlanned"], lights["physicalPercent"]) == (14, 20, 70)
        assert lights["finance"] == {
            "estimated": 400_000, "requested": 400_000, "approved": 350_000,
            "received": 350_000, "spent": 280_000, "awaiting": 0, "balance": 70_000,
            "remaining": 70_000, "financialPercent": 80,
        }
        # Ten points ahead of the work: inside the line, so not flagged.
        assert _flag_codes(lights) == {"partial_approval"}
        assert (lights["linkedGrievances"], lights["residentsAffected"]) == (5, 5)
        assert lights["sabhaMeetingId"] == "sabha_401"
        assert lights["startDate"] == "2026-09-10"
        # History reads in the order it happened, on the days it is said to have.
        assert [e["toStage"] for e in lights["events"] if e["toStage"]] == STAGES
        stamps = [e["createdAt"] for e in lights["events"]]
        assert stamps == sorted(stamps)
        assert stamps[0].startswith("2026-07-10") and stamps[-1].startswith("2026-09-28")

        # Five residents: every one of the five complaints was raised to High.
        assert {g["priority"] for g in lights["grievances"]} == {"High"}
        assert {g["status"] for g in lights["grievances"]} == {"In Progress"}

        # The resident whose login the demo uses can follow it from her own page.
        mine = next(g for g in client.get(f"{API}/grievances", headers=citizen).json()
                    if g["id"] == "grv_demo_light_2")
        assert mine["projectId"] == "proj_demo_streetlights"
        assert mine["similarCount"] == 4

        taps = _project(client, officer, "proj_demo_taps")
        assert taps["stage"] == "budget_requested"
        assert taps["daysInStage"] == (date.today() - date(2026, 7, 20)).days
        assert "stalled" in _flag_codes(taps)

        bins = [g for g in client.get(f"{API}/grievances", headers=officer).json()
                if g["id"].startswith("grv_demo_bin_")]
        assert len(bins) == 3
        assert {(g["status"], g["priority"], g["requestType"], g["projectId"], g["similarCount"])
                for g in bins} == {("Pending", "Medium", "development", None, 2)}

        # Running it again adds nothing.
        with SessionLocal() as db:
            seeder.seed_works_demo(db, today=today)
        assert counts() == (before[0] + 10, before[1] + 2, before[2])
    finally:
        with SessionLocal() as db:
            seeder.remove_works_demo(db)

    assert counts() == before
    with SessionLocal() as db:
        assert db.scalar(select(GrievanceEvent.id).where(
            GrievanceEvent.grievance_id.like("grv_demo_%"))) is None
        assert db.scalar(select(ProjectEvent.id).where(
            ProjectEvent.project_id.like("proj_demo_%"))) is None
