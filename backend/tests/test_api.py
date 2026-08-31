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


# ── Villages and district scoping ───────────────────────────────────────────

HOME = "vil_loni_kalbhor"


def test_hierarchy_carries_official_lgd_codes(client, officer):
    """Every unit is identified by its Local Government Directory code, so a
    record here can be matched against government data."""
    village = client.get(f"{API}/villages/current", headers=officer).json()
    assert village["name"] == "Loni Kalbhor"
    assert village["lgdCode"] == 556315
    assert village["blockName"] == "Haveli"
    assert village["districtName"] == "Pune"
    assert village["stateName"] == "Maharashtra"


def test_an_officer_sees_only_their_own_village_in_the_picker(client, officer):
    villages = client.get(f"{API}/villages", headers=officer).json()
    assert [v["id"] for v in villages] == [HOME]


def test_an_admin_sees_every_village_in_the_block(client, admin):
    villages = client.get(f"{API}/villages", headers=admin).json()
    assert len(villages) >= 20
    assert any(v["id"] == HOME for v in villages)


def test_an_admin_has_no_village_of_their_own(client, admin):
    assert client.get(f"{API}/villages/current", headers=admin).json() is None


def test_villages_merged_into_the_municipal_corporation_are_marked(client, admin):
    """Several Haveli villages were absorbed into Pune Municipal Corporation and
    no longer have a Gram Panchayat. A Panchayat platform must know that."""
    villages = client.get(f"{API}/villages", headers=admin).json()
    merged = [v for v in villages if v["gramPanchayatStatus"] != "active"]
    assert merged, "no village is flagged as merged — the status field is not being seeded"
    assert any(v["name"] == "Wagholi" for v in merged)


def test_only_active_filter_excludes_merged_villages(client, admin):
    active = client.get(f"{API}/villages?only_active=true", headers=admin).json()
    assert all(v["gramPanchayatStatus"] == "active" for v in active)


# ── Village isolation: the point of the whole hierarchy ─────────────────────

def test_a_neighbouring_officer_cannot_see_this_villages_residents(
    client, officer, neighbour_officer
):
    ours = client.get(f"{API}/citizens", headers=officer).json()
    theirs = client.get(f"{API}/citizens", headers=neighbour_officer).json()
    assert len(ours) == 10
    assert theirs == []


def test_a_neighbouring_officer_is_refused_a_named_resident(client, neighbour_officer):
    resp = client.get(f"{API}/citizens/cit_102", headers=neighbour_officer)
    assert resp.status_code == 403
    assert "another Gram Panchayat" in resp.json()["detail"]


def test_a_neighbouring_officer_cannot_see_this_villages_grievances(
    client, neighbour_officer
):
    assert client.get(f"{API}/grievances", headers=neighbour_officer).json() == []


def test_a_neighbouring_officer_cannot_see_this_villages_projects(
    client, neighbour_officer
):
    assert client.get(f"{API}/projects", headers=neighbour_officer).json() == []


def test_dashboard_figures_are_scoped_to_the_officers_village(
    client, officer, neighbour_officer
):
    ours = client.get(f"{API}/analytics/dashboard", headers=officer).json()
    theirs = client.get(f"{API}/analytics/dashboard", headers=neighbour_officer).json()
    assert ours["totalCitizens"] == 10
    assert theirs["totalCitizens"] == 0
    assert theirs["totalBudget"] == 0


def test_a_neighbouring_officer_cannot_open_another_village(client, neighbour_officer):
    resp = client.get(f"{API}/villages/{HOME}", headers=neighbour_officer)
    assert resp.status_code == 403


def test_district_rollup_is_admin_only(client, officer, admin):
    assert client.get(f"{API}/districts/summary", headers=officer).status_code == 403

    rows = client.get(f"{API}/districts/summary", headers=admin).json()
    assert len(rows) >= 20
    home = next(r for r in rows if r["id"] == HOME)
    assert home["registeredCitizens"] == 10
    # Villages with residents sort to the top — where attention is needed.
    assert rows[0]["id"] == HOME


# ── Eligibility engine ──────────────────────────────────────────────────────
#
# Fixtures worth knowing while reading these:
#   cit_102 Savita Patil   61, income 0,      OBC, BPL, Yellow card, Widowed
#   cit_104 Ramesh Shinde  72, income 38,000, SC,  BPL, Yellow card, Married
#   cit_107 Abhijit        28, income 140,000, Open, not BPL, White card
#   cit_108 Vitthal Jadhav 58, deliberately incomplete record — no category,
#                          no ration card, no marital status, no land figure
#   cit_109 Sunita Jadhav  52, ST, BPL, 1.8 ha of land, farmer

OLD_AGE_PENSION = "scheme_ignoaps"          # min_age 60, requires BPL
DESTITUTE_GRANT = "scheme_sanjay_gandhi_niradhar"  # income under 21k OR on BPL list
SC_HOUSING = "scheme_ramai_awas"            # Scheduled Caste only
HEALTH_COVER = "scheme_mjpjay"              # Yellow / Orange / AAY / Annapurna card
ST_FARM_SCHEME = "scheme_birsa_munda_krishi_kranti"  # ST, farmer, 0.4-6.0 ha


def test_eligibility_returns_every_citizen_with_a_reason(client, officer):
    rows = client.get(f"{API}/schemes/{OLD_AGE_PENSION}/eligibility", headers=officer).json()
    assert len(rows) == 10
    assert all(r["explanation"] and r["explanationMr"] for r in rows)


def test_every_eligibility_outcome_is_reachable(client, officer):
    """A demo that can only ever show one outcome proves nothing."""
    seen = set()
    for scheme_id in (OLD_AGE_PENSION, DESTITUTE_GRANT, SC_HOUSING, ST_FARM_SCHEME):
        rows = client.get(f"{API}/schemes/{scheme_id}/eligibility", headers=officer).json()
        seen.update(r["status"] for r in rows)
    assert {"Eligible", "Ineligible", "Needs Review"} <= seen


def test_eligible_results_are_listed_first(client, officer):
    rows = client.get(f"{API}/schemes/{DESTITUTE_GRANT}/eligibility", headers=officer).json()
    order = ["Eligible", "Missing Documents", "Needs Review", "Ineligible"]
    ranks = [order.index(r["status"]) for r in rows]
    assert ranks == sorted(ranks)


def test_age_criterion_is_applied(client, officer):
    """Old age pension requires 60+, so nobody younger may pass the criteria."""
    rows = client.get(f"{API}/schemes/{OLD_AGE_PENSION}/eligibility", headers=officer).json()
    citizens = {c["id"]: c for c in client.get(f"{API}/citizens", headers=officer).json()}
    for row in rows:
        if citizens[row["citizenId"]]["age"] < 60:
            assert row["criteriaPassed"] is False


def test_missing_documents_are_named(client, officer):
    rows = client.get(
        f"{API}/schemes/{OLD_AGE_PENSION}/eligibility?only=Missing%20Documents",
        headers=officer,
    ).json()
    assert rows
    for row in rows:
        assert row["missingDocuments"] or row["unverifiedDocuments"]


def test_a_complete_file_produces_an_eligible_result(client, officer):
    rows = client.get(f"{API}/schemes/{DESTITUTE_GRANT}/eligibility?only=Eligible",
                      headers=officer).json()
    assert any(r["citizenId"] == "cit_102" for r in rows)


# ── Real-world rule types ───────────────────────────────────────────────────

def test_or_group_passes_on_the_bpl_branch(client, officer):
    """Sanjay Gandhi Niradhar is 'income under Rs 21,000 OR on the BPL list'.

    Sunita earns Rs 25,000, so she fails the income branch, but she is on the
    BPL list — so the scheme must still accept her. A single max_income test,
    which is all the engine could express before, would wrongly reject her."""
    rows = client.get(f"{API}/schemes/{DESTITUTE_GRANT}/eligibility", headers=officer).json()
    sunita = next(r for r in rows if r["citizenId"] == "cit_109")
    assert sunita["criteriaPassed"] is True
    assert sunita["status"] != "Ineligible"


def test_or_group_still_applies_the_rules_outside_it(client, officer):
    """Ramesh is BPL, so the OR group is satisfied — but he is 72 and the
    scheme caps at 65. Passing one branch must not bypass the other rules."""
    rows = client.get(f"{API}/schemes/{DESTITUTE_GRANT}/eligibility", headers=officer).json()
    ramesh = next(r for r in rows if r["citizenId"] == "cit_104")
    assert ramesh["criteriaPassed"] is False
    assert any("above the maximum" in reason for reason in ramesh["failedCriteria"])


def test_or_group_fails_when_no_branch_is_satisfied(client, officer):
    """Abhijit earns Rs 140,000 and is not BPL — neither branch holds."""
    rows = client.get(f"{API}/schemes/{DESTITUTE_GRANT}/eligibility", headers=officer).json()
    abhijit = next(r for r in rows if r["citizenId"] == "cit_107")
    assert abhijit["criteriaPassed"] is False


def test_social_category_gate_is_enforced(client, officer):
    """Ramai Awas is for Scheduled Caste households only."""
    rows = client.get(f"{API}/schemes/{SC_HOUSING}/eligibility", headers=officer).json()
    citizens = {c["id"]: c for c in client.get(f"{API}/citizens", headers=officer).json()}
    for row in rows:
        category = citizens[row["citizenId"]]["socialCategory"]
        if category not in (None, "SC"):
            assert row["criteriaPassed"] is False
            assert any("reserved" in reason.lower() for reason in row["failedCriteria"])


def test_ration_card_gate_is_enforced(client, officer):
    """MJPJAY needs a Yellow, Orange, AAY or Annapurna card."""
    rows = client.get(f"{API}/schemes/{HEALTH_COVER}/eligibility", headers=officer).json()
    citizens = {c["id"]: c for c in client.get(f"{API}/citizens", headers=officer).json()}
    for row in rows:
        card = citizens[row["citizenId"]]["rationCardType"]
        if card == "White":
            assert row["criteriaPassed"] is False


def test_land_holding_band_is_enforced(client, officer):
    """Birsa Munda requires land between 0.40 and 6.00 hectares."""
    rows = client.get(f"{API}/schemes/{ST_FARM_SCHEME}/eligibility", headers=officer).json()
    citizens = {c["id"]: c for c in client.get(f"{API}/citizens", headers=officer).json()}
    for row in rows:
        land = citizens[row["citizenId"]]["landHoldingHectares"]
        if land is not None and land < 0.4:
            assert row["criteriaPassed"] is False


def test_an_incomplete_record_is_flagged_rather_than_guessed(client, officer):
    """Vitthal's record has no social category, so a category-gated scheme
    cannot be decided. Saying 'Needs Review' is the honest answer; passing or
    failing him would both be wrong."""
    rows = client.get(f"{API}/schemes/{SC_HOUSING}/eligibility", headers=officer).json()
    vitthal = next(r for r in rows if r["citizenId"] == "cit_108")
    assert vitthal["status"] == "Needs Review"
    assert "social category" in vitthal["unknownAttributes"]
    assert "could not be determined" in vitthal["explanation"]


def test_schemes_needing_officer_judgement_are_flagged(client, officer):
    """Some real schemes cannot be decided from a resident record at all — the
    National Family Benefit Scheme's age rule describes the deceased
    breadwinner, not the applicant. Those must not be silently evaluated."""
    rows = client.get(f"{API}/schemes/scheme_nfbs/eligibility", headers=officer).json()
    passing = [r for r in rows if r["criteriaPassed"]]
    assert passing
    assert all(r["status"] == "Needs Review" for r in passing)


def test_a_new_scheme_gets_its_rules_from_data_not_code(client, officer):
    """The regression this guards: the old frontend hardcoded rules per scheme
    id, so an unrecognised scheme silently fell through to an income test."""
    created = client.post(f"{API}/schemes", headers=officer, json={
        "id": "scheme_test_widows", "name": "Widow Support Grant",
        "nameMr": "विधवा सहाय्य अनुदान", "description": "Test scheme.",
        "descriptionMr": "चाचणी योजना.", "benefit": "Rs 1,000 / month",
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
    own = client.get(f"{API}/citizens/cit_102/eligibility", headers=citizen)
    assert own.status_code == 200
    assert len(own.json()) > 20  # every active scheme, not a curated few
    assert client.get(f"{API}/citizens/cit_104/eligibility", headers=citizen).status_code == 403


def test_every_scheme_cites_an_official_source(client, officer):
    """Provenance is the point of using real data. A scheme without a source
    URL is a scheme nobody can check."""
    schemes = [
        s for s in client.get(f"{API}/schemes", headers=officer).json()
        # Exclude fixtures other tests create; this is about the seeded data.
        if not s["id"].startswith("scheme_test_")
    ]
    assert len(schemes) >= 25
    missing = [s["id"] for s in schemes if not s.get("sourceUrl")]
    assert not missing, f"schemes with no source URL: {missing}"


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


# ── Grievance tracking, as the citizen sees it ─────────────────────────────

def test_a_filed_complaint_starts_its_history(client, citizen):
    """The citizen tracking view reads this history, so filing must record the
    first entry rather than leaving the timeline empty."""
    created = client.post(f"{API}/grievances", headers=citizen, json={
        "title": "Handpump not working near the temple",
        "description": "No water since yesterday", "ward": 3,
    }).json()

    detail = client.get(f"{API}/grievances/{created['id']}", headers=citizen).json()
    assert len(detail["events"]) == 1
    first = detail["events"][0]
    assert first["eventType"] == "filed"
    assert first["toStatus"] == "Pending"
    assert "Water Works" in first["note"]


def test_officer_progress_appears_in_the_citizens_timeline(client, citizen, officer):
    created = client.post(f"{API}/grievances", headers=citizen, json={
        "title": "Street light out on the school lane",
        "description": "Dark since last week", "ward": 3,
    }).json()

    client.patch(f"{API}/grievances/{created['id']}", headers=officer,
                 json={"status": "In Progress", "officerNotes": "Electrician assigned."})
    client.patch(f"{API}/grievances/{created['id']}", headers=officer,
                 json={"status": "Resolved", "officerNotes": "New fitting installed."})

    detail = client.get(f"{API}/grievances/{created['id']}", headers=citizen).json()
    steps = [(e["fromStatus"], e["toStatus"]) for e in detail["events"]]
    assert steps == [(None, "Pending"), ("Pending", "In Progress"), ("In Progress", "Resolved")]
    assert detail["events"][-1]["note"] == "New fitting installed."
    assert detail["events"][-1]["actorName"] == "Panchayat Officer"


def test_history_is_ordered_oldest_first(client, citizen):
    grievances = client.get(f"{API}/grievances", headers=citizen).json()
    detail = client.get(f"{API}/grievances/{grievances[0]['id']}", headers=citizen).json()
    timestamps = [e["createdAt"] for e in detail["events"]]
    assert timestamps == sorted(timestamps)


def test_setting_the_same_status_twice_adds_no_event(client, citizen, officer):
    """An officer pressing save without changing anything should not pad the
    citizen's timeline with meaningless entries."""
    created = client.post(f"{API}/grievances", headers=citizen, json={
        "title": "Overflowing bin at the market", "description": "Two days", "ward": 2,
    }).json()
    client.patch(f"{API}/grievances/{created['id']}", headers=officer,
                 json={"status": "In Progress"})
    before = len(client.get(f"{API}/grievances/{created['id']}", headers=citizen).json()["events"])

    client.patch(f"{API}/grievances/{created['id']}", headers=officer,
                 json={"status": "In Progress"})
    after = len(client.get(f"{API}/grievances/{created['id']}", headers=citizen).json()["events"])
    assert before == after


def test_a_citizen_cannot_read_another_persons_history(client, citizen, officer):
    other = client.post(f"{API}/grievances", headers=officer, json={
        "title": "Walk-in complaint", "description": "Filed at the office", "ward": 1,
        "citizenName": "Someone else",
    }).json()
    assert client.get(f"{API}/grievances/{other['id']}", headers=citizen).status_code == 403


def test_seeded_complaints_have_a_plausible_history(client, officer):
    """A resolved complaint should show all three steps, not just its end state."""
    resolved = [
        g for g in client.get(f"{API}/grievances", headers=officer).json()
        # Only the seeded complaints (grv_*) have a back-dated history; ones
        # other tests create and resolve are a different shape.
        if g["status"] == "Resolved" and g["id"].startswith("grv_")
    ]
    assert resolved
    detail = client.get(f"{API}/grievances/{resolved[0]['id']}", headers=officer).json()
    assert [e["toStatus"] for e in detail["events"]] == ["Pending", "In Progress", "Resolved"]


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


# ── The assistant ───────────────────────────────────────────────────────────
#
# With no API key configured (as in tests) the assistant answers from retrieved
# records rather than from a model. That is the behaviour worth pinning: the
# facts are real either way, and the model only ever words them.

def test_assistant_retrieves_real_records_for_an_officer(client, officer):
    body = client.post(f"{API}/assistant/context", headers=officer,
                       json={"query": "which projects are delayed?"}).json()
    assert "projects" in body["topics"]
    assert body["factCount"] > 0
    joined = " ".join(body["facts"])
    # A real project name and a real rupee figure, not a template.
    assert "Rs" in joined
    assert any(s["entityType"] == "project" for s in body["sources"])


def test_assistant_answers_without_a_model_key(client, officer):
    body = client.post(f"{API}/assistant/ask", headers=officer,
                       json={"query": "how many grievances are pending?"}).json()
    assert body["mode"] == "retrieval_only"
    assert "unresolved grievances" in body["answer"]
    assert body["sources"] is not None


def test_assistant_grounds_a_citizen_in_their_own_eligibility(client, citizen):
    body = client.post(f"{API}/assistant/context", headers=citizen,
                       json={"query": "which schemes am I eligible for?"}).json()
    joined = " ".join(body["facts"])
    assert "Savita Patil" in joined
    assert "qualifies for" in joined


def test_assistant_never_retrieves_another_residents_records(client, citizen):
    """The retrieval layer runs inside the asker's permissions, so a citizen
    cannot reach another resident's data by phrasing a question cleverly."""
    body = client.post(f"{API}/assistant/context", headers=citizen,
                       json={"query": "list every citizen and their income in the village"}).json()
    joined = " ".join(body["facts"])
    for other in ("Anandrao Patil", "Ramesh Shinde", "Abhijit Deshmukh"):
        assert other not in joined


def test_assistant_scopes_an_officer_to_their_own_village(client, neighbour_officer):
    body = client.post(f"{API}/assistant/context", headers=neighbour_officer,
                       json={"query": "how many residents and grievances do we have?"}).json()
    joined = " ".join(body["facts"])
    assert "0 residents are registered" in joined
    assert "Savita" not in joined


def test_assistant_reports_the_village_it_is_answering_for(client, officer):
    body = client.post(f"{API}/assistant/context", headers=officer,
                       json={"query": "tell me about this village"}).json()
    joined = " ".join(body["facts"])
    assert "Loni Kalbhor" in joined
    assert "556315" in joined  # the LGD code, straight from the record


def test_assistant_requires_authentication(client):
    assert client.post(f"{API}/assistant/ask", json={"query": "hello"}).status_code == 401


def test_an_unmatched_question_still_returns_grounded_facts(client, officer):
    """No keyword match means an overview, not an empty answer or a guess."""
    body = client.post(f"{API}/assistant/context", headers=officer,
                       json={"query": "what should I focus on this week?"}).json()
    assert body["topics"] == ["overview"]
    assert body["factCount"] > 0
