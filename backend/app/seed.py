"""Load the demo village into the database.

    python -m app.seed          # insert anything missing, leave existing rows alone
    python -m app.seed --reset  # delete everything first, then reinsert

The source is `app/seed_data.json`, exported from the original React mock data,
so the demo you have been showing survives the move to a real database. This
script also derives what the old flat model could not express: households
become rows in `families`, and each scheme's eligibility rules become a
`criteria` dict the rule engine reads.

Accounts created (password from SEED_DEFAULT_PASSWORD in .env):
    admin@panchayat.gov.in     admin
    officer@panchayat.gov.in   officer
    <first-name>@citizen.panchayat.gov.in citizen, one per seeded citizen
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.models import (
    Citizen,
    CitizenDocument,
    Facility,
    Family,
    Grievance,
    Project,
    SabhaActionItem,
    SabhaMeeting,
    Scheme,
    User,
)
from app.services.classifier import classify

DATA_PATH = Path(__file__).parent / "seed_data.json"

# Eligibility rules, lifted out of the frontend's hardcoded if/else chain and
# expressed as data the engine evaluates.
SCHEME_CRITERIA: dict[str, dict] = {
    "scheme_sr_citizen": {"min_age": 60, "max_income": 100000},
    "scheme_pm_awas": {"max_income": 120000},
    "scheme_krishi_sinchan": {
        "max_income": 200000,
        "occupation_any": ["farmer", "agriculture", "शेतकरी", "शेती"],
    },
    "scheme_beti_bachao": {
        "max_income": 150000,
        "gender": "Female",
        "max_age": 25,
    },
    "scheme_lado_devona": {"min_age": 16, "max_income": 120000, "gender": "Female"},
    "scheme_solar_pump": {
        "min_age": 18,
        "max_income": 250000,
        "occupation_any": ["farmer", "agriculture", "शेतकरी", "शेती"],
    },
}

REQUIRED_DOCS: dict[str, list[dict]] = {
    "scheme_sr_citizen": [
        {"name": "Aadhaar Card", "name_mr": "आधार कार्ड"},
        {"name": "Income Certificate", "name_mr": "उत्पन्नाचा दाखला"},
    ],
    "scheme_pm_awas": [
        {"name": "Income Certificate", "name_mr": "उत्पन्नाचा दाखला"},
        {"name": "Land ownership 7/12 Extract", "name_mr": "७/१२ उतारा"},
    ],
    "scheme_krishi_sinchan": [
        {"name": "Land ownership 7/12 Extract", "name_mr": "७/१२ उतारा"},
        {"name": "Aadhaar Card", "name_mr": "आधार कार्ड"},
    ],
    "scheme_beti_bachao": [
        {"name": "Aadhaar Card", "name_mr": "आधार कार्ड"},
        {"name": "Income Certificate", "name_mr": "उत्पन्नाचा दाखला"},
    ],
}

FAMILY_NAME_MR = {
    "Patil Family": "पाटील कुटुंब",
    "Shinde Family": "शिंदे कुटुंब",
    "Deshmukh Family": "देशमुख कुटुंब",
    "Jadhav Family": "जाधव कुटुंब",
    "Ghadge Family": "घाडगे कुटुंब",
}


def _date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def load_data() -> dict:
    if not DATA_PATH.exists():
        sys.exit(f"Seed file missing: {DATA_PATH}")
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def reset(db: Session) -> None:
    """Delete in dependency order so foreign keys never block the wipe."""
    for model in (
        SabhaActionItem, SabhaMeeting, CitizenDocument, Grievance,
        Facility, Project, Scheme, User, Citizen, Family,
    ):
        db.execute(delete(model))
    db.commit()
    print("Cleared existing rows.")


def seed_families(db: Session, data: dict) -> None:
    seen: dict[str, tuple[str, int]] = {}
    for c in data["citizens"]:
        seen.setdefault(c["familyId"], (c["familyName"], c["ward"]))

    for family_id, (name, ward) in seen.items():
        if db.get(Family, family_id):
            continue
        db.add(Family(
            id=family_id, name=name,
            name_mr=FAMILY_NAME_MR.get(name, name), ward=ward,
        ))
    db.commit()
    print(f"Families: {len(seen)}")


def seed_citizens(db: Session, data: dict) -> None:
    # The old model stored relationships only on the head's `familyMembers`
    # list, so rebuild each member's own relation from it.
    relations: dict[str, tuple[str, str]] = {}
    heads: set[str] = set()
    for c in data["citizens"]:
        if c.get("familyMembers"):
            heads.add(c["id"])
            for m in c["familyMembers"]:
                relations[m["id"]] = (m.get("relation", ""), m.get("relationMr", ""))

    count = 0
    for c in data["citizens"]:
        if db.get(Citizen, c["id"]):
            continue
        relation, relation_mr = relations.get(c["id"], ("Household Head", "कुटुंब प्रमुख"))
        db.add(Citizen(
            id=c["id"], name=c["name"], name_mr=c["nameMr"], age=c["age"],
            gender=c["gender"], gender_mr=c["genderMr"],
            occupation=c["occupation"], occupation_mr=c["occupationMr"],
            income=c["income"], ward=c["ward"], phone=c.get("phone"),
            family_id=c["familyId"], relation=relation, relation_mr=relation_mr,
            is_head=c["id"] in heads,
        ))
        count += 1
    db.commit()
    print(f"Citizens: {count}")


def seed_schemes(db: Session, data: dict) -> None:
    count = 0
    for s in data["schemes"]:
        if db.get(Scheme, s["id"]):
            continue
        criteria = dict(SCHEME_CRITERIA.get(s["id"], {}))
        # Fall back to whatever the old flat fields said, so a scheme without an
        # explicit rule set still gets its age/income bounds.
        criteria.setdefault("min_age", s.get("minAge"))
        criteria.setdefault("max_income", s.get("maxIncome"))
        if s.get("genderRestriction"):
            criteria.setdefault("gender", s["genderRestriction"])
        criteria = {k: v for k, v in criteria.items() if v is not None}

        db.add(Scheme(
            id=s["id"], name=s["name"], name_mr=s["nameMr"],
            description=s["description"], description_mr=s["descriptionMr"],
            benefit=s["benefit"], benefit_mr=s["benefitMr"],
            criteria=criteria,
            required_documents=REQUIRED_DOCS.get(s["id"], []),
            status="active", is_government_feed=False,
            form_url=s.get("formUrl"),
        ))
        count += 1

    # The state feed: schemes awaiting an officer's adopt/reject decision.
    for s in data["feed"]:
        if db.get(Scheme, s["id"]):
            continue
        criteria = dict(SCHEME_CRITERIA.get(s["id"], {}))
        criteria.setdefault("min_age", s.get("minAge"))
        criteria.setdefault("max_income", s.get("maxIncome"))
        if s.get("genderRestriction"):
            criteria.setdefault("gender", s["genderRestriction"])
        criteria = {k: v for k, v in criteria.items() if v is not None}

        db.add(Scheme(
            id=s["id"], name=s["name"], name_mr=s["nameMr"],
            description=s["description"], description_mr=s["descriptionMr"],
            benefit=s["benefit"], benefit_mr=s["benefitMr"],
            criteria=criteria, required_documents=[],
            status="pending", is_government_feed=True,
            source_gov=s.get("sourceGov"), form_url=s.get("formUrl"),
        ))
        count += 1
    db.commit()
    print(f"Schemes: {count}")


def seed_grievances(db: Session, data: dict) -> None:
    by_name = {c.name: c for c in db.query(Citizen).all()}
    count = 0
    for g in data["grievances"]:
        if db.get(Grievance, g["id"]):
            continue
        coords = g.get("coordinates") or [None, None]
        # Department wasn't classified consistently in the mock data; recompute
        # it from the same classifier the API uses so routing is uniform.
        result = classify(g["title"], g.get("description", ""))
        citizen = by_name.get(g.get("citizenName", ""))

        db.add(Grievance(
            id=g["id"], title=g["title"], title_mr=g["titleMr"],
            description=g["description"], description_mr=g["descriptionMr"],
            category=g["category"], category_mr=g["categoryMr"],
            priority=g["priority"], priority_mr=g["priorityMr"],
            status=g["status"], status_mr=g["statusMr"],
            department=g.get("deptName") or result.department,
            department_mr=g.get("deptNameMr") or result.department_mr,
            ward=g["ward"], latitude=coords[0], longitude=coords[1],
            citizen_id=citizen.id if citizen else None,
            citizen_name=g.get("citizenName") or "Walk-in complainant",
            phone=g.get("phone"),
            submitted_date=_date(g.get("submittedDate")) or date.today(),
            officer_notes=g.get("officerNotes"),
            auto_classified=False,
        ))
        count += 1
    db.commit()
    print(f"Grievances: {count}")


def seed_projects(db: Session, data: dict) -> None:
    count = 0
    for p in data["projects"]:
        if db.get(Project, p["id"]):
            continue
        lat, lng = p.get("coordinates") or [0.0, 0.0]
        db.add(Project(
            id=p["id"], name=p["name"], name_mr=p["nameMr"],
            description=p["description"], description_mr=p["descriptionMr"],
            progress=p["progress"], budget=p["budget"], utilized=p["utilized"],
            status=p["status"], status_mr=p["statusMr"], ward=p["ward"],
            location=p["location"], location_mr=p["locationMr"],
            latitude=lat, longitude=lng,
        ))
        count += 1
    db.commit()
    print(f"Projects: {count}")


# The original mock data shipped only three documents, none of them an Aadhaar
# card — so no citizen could ever reach "Eligible" for a scheme that requires
# one, and the demo could only ever show two of the three states. These rows
# complete a few files so all three outcomes are visible. `doc_102` in the mock
# data also referenced "Amit Shinde", who is not in the citizen list at all.
DEMO_DOCUMENTS = [
    ("doc_201", "Anandrao Patil", "Aadhaar Card", "आधार कार्ड",
     "aadhaar_anandrao.pdf", "Verified", "पडताळणी पूर्ण"),
    ("doc_202", "Anandrao Patil", "Income Certificate", "उत्पन्नाचा दाखला",
     "income_certificate_anandrao.pdf", "Verified", "पडताळणी पूर्ण"),
    ("doc_203", "Savita Patil", "Aadhaar Card", "आधार कार्ड",
     "aadhaar_savita.pdf", "Verified", "पडताळणी पूर्ण"),
    ("doc_204", "Ramesh Shinde", "Aadhaar Card", "आधार कार्ड",
     "aadhaar_ramesh.pdf", "Rejected", "नाकारले"),
]


def seed_documents(db: Session, data: dict) -> None:
    by_name = {c.name: c for c in db.query(Citizen).all()}
    count = 0

    for doc_id, citizen_name, doc_type, doc_type_mr, file_name, st, st_mr in DEMO_DOCUMENTS:
        citizen = by_name.get(citizen_name)
        if citizen is None or db.get(CitizenDocument, doc_id):
            continue
        db.add(CitizenDocument(
            id=doc_id, citizen_id=citizen.id, doc_type=doc_type,
            doc_type_mr=doc_type_mr, file_name=file_name,
            status=st, status_mr=st_mr, submitted_date=date(2026, 8, 5),
            rejection_reason="Photograph is not legible." if st == "Rejected" else None,
        ))
        count += 1

    for d in data["docs"]:
        if db.get(CitizenDocument, d["id"]):
            continue
        citizen = by_name.get(d["citizenName"])
        if citizen is None:
            print(f"  ! skipping {d['id']}: no citizen named {d['citizenName']}")
            continue
        db.add(CitizenDocument(
            id=d["id"], citizen_id=citizen.id,
            doc_type=d["docType"], doc_type_mr=d["docTypeMr"],
            file_name=d["fileName"], status=d["status"], status_mr=d["statusMr"],
            submitted_date=_date(d.get("submittedDate")) or date.today(),
        ))
        count += 1
    db.commit()
    print(f"Documents: {count}")


def seed_sabha(db: Session, data: dict) -> None:
    m = data["sabha"]
    if db.get(SabhaMeeting, m["id"]):
        print("Sabha meeting: already present")
        return

    db.add(SabhaMeeting(
        id=m["id"], meeting_date=_date(m.get("date")) or date.today(),
        title=m["title"], title_mr=m["titleMr"],
        summary=m["summary"], summary_mr=m["summaryMr"],
        decisions=m.get("decisions", []), decisions_mr=m.get("decisionsMr", []),
        extracted_by="manual",
    ))
    db.flush()

    for i, item in enumerate(m.get("actionItems", []), start=1):
        db.add(SabhaActionItem(
            id=f"act_{m['id']}_{i:02d}", meeting_id=m["id"],
            action=item["action"], action_mr=item["actionMr"],
            responsible=item["responsible"], responsible_mr=item["responsibleMr"],
            deadline=_date(item.get("deadline")),
            status=item["status"], status_mr=item["statusMr"],
        ))
    db.commit()
    print(f"Sabha meeting: 1 with {len(m.get('actionItems', []))} action items")


def seed_facilities(db: Session, data: dict) -> None:
    count = 0
    for f in data["facilities"]:
        if db.get(Facility, f["id"]):
            continue
        lat, lng = f["coordinates"]
        db.add(Facility(
            id=f["id"], name=f["name"], name_mr=f["nameMr"],
            facility_type=f["type"], latitude=lat, longitude=lng,
            details=f.get("details"),
        ))
        count += 1
    db.commit()
    print(f"Facilities: {count}")


def seed_users(db: Session) -> None:
    password = hash_password(settings.SEED_DEFAULT_PASSWORD)
    created = 0

    for user_id, email, name, role in [
        ("usr_admin", "admin@panchayat.gov.in", "System Administrator", "admin"),
        ("usr_officer", "officer@panchayat.gov.in", "Panchayat Officer", "officer"),
    ]:
        if db.get(User, user_id):
            continue
        db.add(User(id=user_id, email=email, hashed_password=password,
                    full_name=name, role=role))
        created += 1

    # One login per citizen, so the portal can be demonstrated as that person.
    for citizen in db.query(Citizen).all():
        user_id = f"usr_{citizen.id}"
        if db.get(User, user_id):
            continue
        # Not a .local address: email-validator rejects special-use domains,
        # so a seeded citizen would be unable to sign in.
        handle = citizen.name.split()[0].lower()
        db.add(User(
            id=user_id, email=f"{handle}@citizen.panchayat.gov.in",
            hashed_password=password,
            full_name=citizen.name, role="citizen", citizen_id=citizen.id,
        ))
        created += 1

    db.commit()
    print(f"Users: {created}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the E-Panchayat database.")
    parser.add_argument("--reset", action="store_true",
                        help="delete all existing rows before seeding")
    parser.add_argument("--create-tables", action="store_true",
                        help="create tables directly instead of running Alembic")
    args = parser.parse_args()

    if args.create_tables:
        Base.metadata.create_all(engine)
        print("Tables created.")

    data = load_data()
    with SessionLocal() as db:
        if args.reset:
            reset(db)
        seed_families(db, data)
        seed_citizens(db, data)
        seed_schemes(db, data)
        seed_grievances(db, data)
        seed_projects(db, data)
        seed_documents(db, data)
        seed_sabha(db, data)
        seed_facilities(db, data)
        seed_users(db)

    print(f"\nDone. Sign in as officer@panchayat.gov.in / {settings.SEED_DEFAULT_PASSWORD}")


if __name__ == "__main__":
    main()
