"""Reading a Government Resolution into a scheme.

The model call needs a key and a network, so these test the part that decides
whether an extraction is safe to store: the criteria sanitiser. That logic is
what stands between "a model misread a GR" and "the Panchayat told the wrong
people to apply for a pension".
"""

import pytest

from app.services.eligibility import evaluate  # noqa: F401  (import guards the vocabulary)
from app.services.scheme_reader import (
    KNOWN_CRITERIA,
    SchemeExtractionError,
    _clean_criteria,
    _parse_date,
)

API = "/api/v1"


# ── The criteria vocabulary must not drift ──────────────────────────────────

def test_every_known_criterion_is_one_the_engine_evaluates():
    """If the reader can propose a rule the engine ignores, a scheme looks
    stricter than it behaves. This test fails the moment the two lists drift."""
    from pathlib import Path

    # Resolved from this file and read as UTF-8 rather than left to the
    # platform: the engine is full of Marathi and rupee signs, and on Windows
    # the default cp1252 decode fails outright.
    engine = (
        Path(__file__).resolve().parents[1] / "app" / "services" / "eligibility.py"
    ).read_text(encoding="utf-8")
    for key in KNOWN_CRITERIA:
        assert f'"{key}"' in engine, (
            f"{key} is offered to the reader but never read by the eligibility "
            f"engine, so a scheme using it would silently have no such rule"
        )


# ── Sanitising what the model returns ───────────────────────────────────────

def test_known_criteria_are_kept():
    kept, dropped = _clean_criteria({"min_age": 60, "max_income": 100000})
    assert kept == {"min_age": 60, "max_income": 100000}
    assert dropped == []


def test_an_unknown_criterion_is_dropped_and_reported():
    """The dangerous case: a rule that reads as configured but tests nothing."""
    kept, dropped = _clean_criteria({"min_age": 60, "must_own_goat": True})
    assert kept == {"min_age": 60}
    assert len(dropped) == 1
    assert "must_own_goat" in dropped[0]


def test_empty_values_are_not_stored_as_rules():
    """A criterion set to null or an empty list is not a restriction. Storing it
    would show the officer a rule that does nothing."""
    kept, _ = _clean_criteria(
        {"min_age": 60, "gender": None, "category_any": [], "occupation_any": ""}
    )
    assert kept == {"min_age": 60}


def test_a_non_dict_is_handled_rather_than_crashing():
    assert _clean_criteria(None) == ({}, [])
    assert _clean_criteria("min_age 60") == ({}, [])


def test_falsy_but_meaningful_values_survive():
    """requires_bpl=False and min_age=0 are real statements, not absences."""
    kept, _ = _clean_criteria({"requires_bpl": False, "min_age": 0})
    assert kept == {"requires_bpl": False, "min_age": 0}


# ── Dates ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "raw,expected",
    [
        ("2026-04-01", "2026-04-01"),
        ("01-04-2026", "2026-04-01"),
        ("01/04/2026", "2026-04-01"),
        ("2026/04/01", "2026-04-01"),
    ],
)
def test_dates_are_read_in_the_formats_a_gr_actually_uses(raw, expected):
    parsed = _parse_date(raw)
    assert parsed is not None and parsed.isoformat() == expected


def test_an_unparseable_date_is_dropped_not_guessed():
    """'the first Monday of April' becomes no date, not a made-up one."""
    assert _parse_date("first Monday of April") is None
    assert _parse_date("") is None
    assert _parse_date(None) is None


# ── The endpoint ─────────────────────────────────────────────────────────────

def test_reading_a_gr_is_officer_only(client, citizen):
    resp = client.post(
        f"{API}/schemes/read",
        headers=citizen,
        files={"file": ("gr.txt", b"x" * 200, "text/plain")},
    )
    assert resp.status_code == 403


def test_an_unreadable_file_type_is_refused_with_advice(client, officer):
    resp = client.post(
        f"{API}/schemes/read",
        headers=officer,
        files={"file": ("scan.jpg", b"\xff\xd8\xff" + b"x" * 200, "image/jpeg")},
    )
    assert resp.status_code == 400
    assert "PDF" in resp.json()["detail"]


def test_a_file_with_no_readable_text_says_so(client, officer):
    resp = client.post(
        f"{API}/schemes/read",
        headers=officer,
        files={"file": ("empty.txt", b"short", "text/plain")},
    )
    assert resp.status_code == 400
    assert "readable text" in resp.json()["detail"].lower()


def test_without_a_key_the_endpoint_refuses_rather_than_inventing(client, officer):
    """The test environment has no GEMINI_API_KEY. The reader must fail loudly
    and tell the officer what to do, not fabricate a scheme."""
    body = (
        "GOVERNMENT OF MAHARASHTRA\nGovernment Resolution No. 2026/CR-14\n"
        "Subject: Old age pension enhancement for residents above sixty years "
        "with annual household income below one lakh rupees.\n" * 3
    ).encode()
    resp = client.post(
        f"{API}/schemes/read",
        headers=officer,
        files={"file": ("gr.txt", body, "text/plain")},
    )
    assert resp.status_code == 503
    assert "GEMINI_API_KEY" in resp.json()["detail"]


def test_a_read_scheme_never_reaches_citizens_before_approval(client, officer, citizen):
    """A pending scheme must not appear in any citizen-facing list. This is the
    property the whole review gate exists to provide."""
    from sqlalchemy import select

    from app.db.session import SessionLocal
    from app.models import Scheme

    with SessionLocal() as db:
        db.add(
            Scheme(
                id="scheme_gr_pending_test",
                name="Unapproved Test Scheme",
                name_mr="चाचणी योजना",
                description="Proposed by the document reader, not yet approved.",
                description_mr="अद्याप मंजूर नाही.",
                benefit="₹1,000 per month",
                benefit_mr="दरमहा ₹१,०००",
                criteria={"min_age": 1},  # everyone would pass this
                status="pending",
                is_government_feed=True,
            )
        )
        db.commit()

    try:
        listed = client.get(f"{API}/schemes", headers=citizen).json()
        assert all(s["id"] != "scheme_gr_pending_test" for s in listed)

        # And it must not tell anyone they are eligible for it either.
        me = client.get(f"{API}/auth/me", headers=citizen).json()
        results = client.get(
            f"{API}/citizens/{me['citizenId']}/eligibility", headers=citizen
        ).json()
        assert all(r["schemeId"] != "scheme_gr_pending_test" for r in results)

        # The officer reviewing the feed does see it — that is the point.
        feed = client.get(f"{API}/schemes/feed", headers=officer).json()
        assert any(s["id"] == "scheme_gr_pending_test" for s in feed)
    finally:
        with SessionLocal() as db:
            row = db.scalar(select(Scheme).where(Scheme.id == "scheme_gr_pending_test"))
            if row:
                db.delete(row)
                db.commit()


def test_scheme_extraction_error_exists_for_a_document_that_is_not_a_scheme():
    with pytest.raises(SchemeExtractionError):
        raise SchemeExtractionError("not a scheme")
