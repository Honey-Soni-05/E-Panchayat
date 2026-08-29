"""API behaviour tests.

The access-control tests below are the ones worth reading first: they pin the
behaviour that the previous version got wrong, where typing any citizen ID at
the login screen opened that resident's file.
"""

from tests.conftest import API


# ── Health and auth ─────────────────────────────────────────────────────────

def test_health_reports_database_and_ai_state(client):
    body = client.get("/health").json()
    assert body["database"] == "connected"
    assert body["aiEnabled"] is False  # no key configured in tests


def test_login_rejects_a_wrong_password(client):
    resp = client.post(
        f"{API}/auth/login",
        json={"email": "officer@panchayat.gov.in", "password": "not-it"},
    )
    assert resp.status_code == 401


def test_login_does_not_reveal_whether_an_account_exists(client):
    unknown = client.post(
        f"{API}/auth/login",
        json={"email": "nobody@panchayat.gov.in", "password": "whatever"},
    )
    wrong = client.post(
        f"{API}/auth/login",
        json={"email": "officer@panchayat.gov.in", "password": "whatever"},
    )
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()["detail"] == wrong.json()["detail"]


def test_citizen_login_is_bound_to_one_record(client, citizen):
    me = client.get(f"{API}/auth/me", headers=citizen).json()
    assert me["role"] == "citizen"
    assert me["citizenId"] == "cit_102"


def test_refresh_token_issues_a_new_access_token(client):
    tokens = client.post(
        f"{API}/auth/login",
        json={"email": "officer@panchayat.gov.in", "password": "Test@12345"},
    ).json()
    resp = client.post(f"{API}/auth/refresh", json={"refreshToken": tokens["refreshToken"]})
    assert resp.status_code == 200
    assert resp.json()["accessToken"]


def test_an_access_token_is_not_accepted_as_a_refresh_token(client, officer):
    token = officer["Authorization"].removeprefix("Bearer ")
    assert client.post(f"{API}/auth/refresh", json={"refreshToken": token}).status_code == 401


# ── Access control ──────────────────────────────────────────────────────────

def test_unauthenticated_requests_are_rejected(client):
    assert client.get(f"{API}/citizens").status_code == 401
    assert client.get(f"{API}/analytics/dashboard").status_code == 401


def test_officer_sees_every_citizen(client, officer):
    assert len(client.get(f"{API}/citizens", headers=officer).json()) == 10


def test_citizen_sees_only_their_own_record(client, citizen):
    rows = client.get(f"{API}/citizens", headers=citizen).json()
    assert [r["id"] for r in rows] == ["cit_102"]


def test_citizen_cannot_open_another_residents_file(client, citizen):
    assert client.get(f"{API}/citizens/cit_104", headers=citizen).status_code == 403


def test_citizen_cannot_reach_officer_analytics(client, citizen):
    assert client.get(f"{API}/analytics/dashboard", headers=citizen).status_code == 403


def test_citizen_cannot_create_records(client, citizen):
    resp = client.post(f"{API}/citizens", headers=citizen, json={
        "name": "Intruder", "nameMr": "घुसखोर", "age": 30, "gender": "Male",
        "genderMr": "पुरुष", "occupation": "None", "occupationMr": "नाही",
        "income": 0, "ward": 1,
    })
    assert resp.status_code == 403


# ── Citizens ────────────────────────────────────────────────────────────────

def test_family_details_are_rebuilt_from_the_families_table(client, officer):
    """The old model denormalised this onto every row, which is what broke when
    cloud data replaced the local array."""
    body = client.get(f"{API}/citizens/cit_101", headers=officer).json()
    assert body["familyName"] == "Patil Family"
    assert len(body["familyMembers"]) == 2
    assert body["id"] not in [m["id"] for m in body["familyMembers"]]


def test_citizen_search_matches_name_and_id(client, officer):
    by_name = client.get(f"{API}/citizens?search=shinde", headers=officer).json()
    assert len(by_name) >= 2
    by_id = client.get(f"{API}/citizens?search=cit_101", headers=officer).json()
    assert len(by_id) == 1


def test_officer_can_create_and_update_a_citizen(client, officer):
    created = client.post(f"{API}/citizens", headers=officer, json={
        "id": "cit_test_900", "name": "Test Resident", "nameMr": "चाचणी रहिवासी",
        "age": 40, "gender": "Female", "genderMr": "महिला",
        "occupation": "Teacher", "occupationMr": "शिक्षिका",
        "income": 90000, "ward": 2,
    })
    assert created.status_code == 201

    updated = client.patch(f"{API}/citizens/cit_test_900", headers=officer,
                           json={"income": 45000})
    assert updated.json()["income"] == 45000

    assert client.delete(f"{API}/citizens/cit_test_900", headers=officer).status_code == 204


# ── Eligibility engine ──────────────────────────────────────────────────────

def test_eligibility_returns_every_citizen_with_a_reason(client, officer):
    rows = client.get(f"{API}/schemes/scheme_sr_citizen/eligibility", headers=officer).json()
    assert len(rows) == 10
    assert all(r["explanation"] and r["explanationMr"] for r in rows)


def test_all_three_eligibility_outcomes_are_reachable(client, officer):
    rows = client.get(f"{API}/schemes/scheme_sr_citizen/eligibility", headers=officer).json()
    assert {r["status"] for r in rows} == {"Eligible", "Missing Documents", "Ineligible"}


def test_eligible_results_are_listed_first(client, officer):
    rows = client.get(f"{API}/schemes/scheme_sr_citizen/eligibility", headers=officer).json()
    rank = {"Eligible": 0, "Missing Documents": 1, "Ineligible": 2}
    assert [rank[r["status"]] for r in rows] == sorted(rank[r["status"]] for r in rows)


def test_age_criterion_is_applied(client, officer):
    """Senior pension needs age 60+, so nobody younger may pass the criteria."""
    rows = client.get(f"{API}/schemes/scheme_sr_citizen/eligibility", headers=officer).json()
    citizens = {
        c["id"]: c for c in client.get(f"{API}/citizens", headers=officer).json()
    }
    for row in rows:
        if citizens[row["citizenId"]]["age"] < 60:
            assert row["criteriaPassed"] is False


def test_missing_documents_are_named(client, officer):
    rows = client.get(
        f"{API}/schemes/scheme_sr_citizen/eligibility?only=Missing%20Documents",
        headers=officer,
    ).json()
    assert rows
    for row in rows:
        assert row["missingDocuments"] or row["unverifiedDocuments"]


def test_a_new_scheme_gets_its_rules_from_data_not_code(client, officer):
    """The regression this guards: the old frontend hardcoded rules per scheme
    id, so an unrecognised scheme silently fell through to an income test."""
    created = client.post(f"{API}/schemes", headers=officer, json={
        "id": "scheme_test_widows", "name": "Widow Support Grant",
        "nameMr": "विधवा सहाय्य अनुदान", "description": "Test scheme.",
        "descriptionMr": "चाचणी योजना.", "benefit": "₹1,000 / month",
        "benefitMr": "₹१,००० / महिना",
        "criteria": {"gender": "Female", "min_age": 55, "max_income": 50000},
        "requiredDocuments": [],
    })
    assert created.status_code == 201

    rows = client.get(f"{API}/schemes/scheme_test_widows/eligibility", headers=officer).json()
    for row in rows:
        if row["criteriaPassed"]:
            citizen = client.get(f"{API}/citizens/{row['citizenId']}", headers=officer).json()
            assert citizen["gender"] == "Female"
            assert citizen["age"] >= 55
            assert citizen["income"] <= 50000


def test_citizen_sees_own_eligibility_but_not_others(client, citizen):
    assert client.get(f"{API}/citizens/cit_102/eligibility", headers=citizen).status_code == 200
    assert client.get(f"{API}/citizens/cit_104/eligibility", headers=citizen).status_code == 403


# ── Grievance classification and workflow ───────────────────────────────────

def test_classifier_picks_category_priority_and_department(client, citizen):
    body = client.post(f"{API}/grievances/classify", headers=citizen, json={
        "title": "Sewage water mixing into the drinking pipeline near the school",
        "description": "Urgent, children are falling sick",
        "ward": 3,
    }).json()
    assert body["category"] == "Water"
    assert body["priority"] == "Critical"
    assert body["department"] == "Water Works Department"


def test_classifier_defaults_unmatched_text_to_other(client, citizen):
    body = client.post(f"{API}/grievances/classify", headers=citizen, json={
        "title": "Query about the office timings", "description": "", "ward": 1,
    }).json()
    assert body["category"] == "Other"


def test_citizen_files_a_grievance_that_is_linked_and_classified(client, citizen):
    body = client.post(f"{API}/grievances", headers=citizen, json={
        "title": "Streetlight pole broken on the main lane",
        "description": "It is dark at night", "ward": 3,
    })
    assert body.status_code == 201
    payload = body.json()
    assert payload["citizenId"] == "cit_102"
    assert payload["category"] == "Electricity"
    assert payload["autoClassified"] is True
    assert payload["status"] == "Pending"


def test_officer_override_clears_the_auto_classified_flag(client, officer):
    grievance = client.post(f"{API}/grievances", headers=officer, json={
        "title": "Broken hand pump", "description": "No water", "ward": 2,
        "citizenName": "Walk-in complainant",
    }).json()
    updated = client.patch(f"{API}/grievances/{grievance['id']}", headers=officer,
                           json={"priority": "Low"}).json()
    assert updated["priority"] == "Low"
    assert updated["autoClassified"] is False


def test_only_an_officer_can_resolve_a_grievance(client, officer, citizen):
    grievance = client.post(f"{API}/grievances", headers=citizen, json={
        "title": "Garbage not collected", "description": "Two weeks now", "ward": 3,
    }).json()

    assert client.patch(f"{API}/grievances/{grievance['id']}", headers=citizen,
                        json={"status": "Resolved"}).status_code == 403

    resolved = client.patch(f"{API}/grievances/{grievance['id']}", headers=officer,
                            json={"status": "Resolved", "officerNotes": "Collected"}).json()
    assert resolved["status"] == "Resolved"
    assert resolved["resolvedDate"] is not None


def test_citizens_only_see_their_own_grievances(client, citizen, officer):
    mine = client.get(f"{API}/grievances", headers=citizen).json()
    everything = client.get(f"{API}/grievances", headers=officer).json()
    assert all(g["citizenId"] == "cit_102" for g in mine)
    assert len(everything) > len(mine)


# ── Projects ────────────────────────────────────────────────────────────────

def test_full_progress_marks_a_project_completed(client, officer):
    body = client.patch(f"{API}/projects/proj_303", headers=officer,
                        json={"progress": 100}).json()
    assert body["status"] == "Completed"
    assert body["statusMr"] == "पूर्ण झालेले"


def test_spending_beyond_the_sanctioned_budget_is_refused(client, officer):
    resp = client.patch(f"{API}/projects/proj_302", headers=officer,
                        json={"utilized": 99_000_000})
    assert resp.status_code == 400


# ── Analytics ───────────────────────────────────────────────────────────────

def test_dashboard_counts_come_from_the_database(client, officer):
    body = client.get(f"{API}/analytics/dashboard", headers=officer).json()
    assert body["totalCitizens"] == 10
    assert body["totalFamilies"] == 5
    assert body["totalBudget"] > 0


def test_budget_series_is_reported_in_lakhs(client, officer):
    rows = client.get(f"{API}/analytics/project-budgets", headers=officer).json()
    assert rows
    assert all(row["budgetLakh"] < 1000 for row in rows)


# ── Gram Sabha ──────────────────────────────────────────────────────────────

def test_seeded_meeting_has_normalised_action_items(client, officer):
    meetings = client.get(f"{API}/sabha/meetings", headers=officer).json()
    assert len(meetings) == 1
    assert len(meetings[0]["actionItems"]) == 3


def test_action_item_status_can_be_toggled(client, officer):
    meeting = client.get(f"{API}/sabha/meetings", headers=officer).json()[0]
    item_id = meeting["actionItems"][0]["id"]
    body = client.patch(f"{API}/sabha/action-items/{item_id}", headers=officer,
                        json={"status": "Completed"}).json()
    assert body["status"] == "Completed"


def test_transcript_upload_fails_loudly_without_an_api_key(client, officer):
    """The old build silently returned canned text here. It must now say why
    it cannot help."""
    resp = client.post(
        f"{API}/sabha/meetings/process",
        headers=officer,
        files={"file": ("minutes.txt", b"Gram Sabha minutes. " * 20, "text/plain")},
        data={"meetingDate": "2026-08-20"},
    )
    assert resp.status_code == 503
    assert "GEMINI_API_KEY" in resp.json()["detail"]


def test_unreadable_transcript_is_rejected_before_the_model_is_called(client, officer):
    resp = client.post(
        f"{API}/sabha/meetings/process",
        headers=officer,
        files={"file": ("scan.xyz", b"binary junk", "application/octet-stream")},
        data={"meetingDate": "2026-08-20"},
    )
    assert resp.status_code == 400
