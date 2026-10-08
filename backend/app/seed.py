"""Load the demo village into the database.

    python -m app.seed          # insert anything missing, leave existing rows alone
    python -m app.seed --reset  # delete everything first, then reinsert

    python -m app.seed --refresh-works-demo   # rebuild the works demo, dated from today
    python -m app.seed --remove-works-demo    # take the works demo out and stop

The source is `app/seed_data.json`, exported from the original React mock data,
so the demo you have been showing survives the move to a real database. This
script also derives what the old flat model could not express: households
become rows in `families`, and each scheme's eligibility rules become a
`criteria` dict the rule engine reads.

Accounts created (password from SEED_DEFAULT_PASSWORD in .env):
    admin@panchayat.gov.in     admin
    officer@panchayat.gov.in   officer
    <first-name>@citizen.panchayat.gov.in citizen, one per seeded citizen
                               except the residents in UNREGISTERED_CITIZEN_IDS
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core import clock
from app.core.config import settings
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import SessionLocal, engine
from app.sample_docs import write_sample
from app.models import (
    Block,
    BudgetEntry,
    Citizen,
    CitizenDocument,
    Facility,
    Family,
    Grievance,
    GrievanceEvent,
    KnowledgeChunk,
    Project,
    ProjectEvent,
    SabhaActionItem,
    SabhaMeeting,
    Scheme,
    State,
    District,
    User,
    Village,
)
from app.services import demand, timeline, works
from app.services.classifier import classify

# Must match UPLOAD_ROOT in app/api/routes/documents.py, or the seeder writes
# files the download endpoint cannot find.
UPLOAD_ROOT = Path("uploads/documents")

DATA_PATH = Path(__file__).parent / "seed_data.json"
VILLAGES_PATH = Path(__file__).parent / "villages_data.json"

# The Gram Panchayat this demo's residents, projects and grievances belong to.
HOME_VILLAGE_ID = "vil_loni_kalbhor"

# Official Local Government Directory codes, verified against the LGD dump.
HIERARCHY = {
    "state": dict(id="st_maharashtra", name="Maharashtra", name_mr="महाराष्ट्र", lgd_code=27),
    "district": dict(id="dist_pune", name="Pune", name_mr="पुणे", lgd_code=490),
    "block": dict(id="blk_haveli", name="Haveli", name_mr="हवेली", lgd_code=4193),
}

# Eligibility rules and required documents now live in seed_data.json, one set
# per scheme, researched from official government sources with a source_url on
# each record. They are no longer hardcoded here.

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
        BudgetEntry, ProjectEvent, CitizenDocument, GrievanceEvent, Grievance,
        Facility, Project, SabhaActionItem, SabhaMeeting, Scheme, User, Citizen,
        Family, Village, Block, District, State,
    ):
        db.execute(delete(model))
    db.commit()
    print("Cleared existing rows.")


def slugify(name: str) -> str:
    return "vil_" + "".join(ch if ch.isalnum() else "_" for ch in name.lower()).strip("_")


def seed_hierarchy(db: Session) -> None:
    """State, district and block, with their real LGD codes."""
    if not db.get(State, HIERARCHY["state"]["id"]):
        db.add(State(**HIERARCHY["state"]))
    if not db.get(District, HIERARCHY["district"]["id"]):
        db.add(District(**HIERARCHY["district"], state_id=HIERARCHY["state"]["id"]))
    if not db.get(Block, HIERARCHY["block"]["id"]):
        db.add(Block(**HIERARCHY["block"], district_id=HIERARCHY["district"]["id"]))
    db.commit()
    print("Hierarchy: Maharashtra (27) > Pune (490) > Haveli (4193)")


def seed_villages(db: Session) -> None:
    """Real Gram Panchayats of Haveli taluka, from the Local Government Directory.

    `gram_panchayat_status` is not cosmetic: several of these villages were
    absorbed into Pune Municipal Corporation in 2017 and 2021 and no longer have
    a Gram Panchayat, which a Panchayat platform has to know.
    """
    if not VILLAGES_PATH.exists():
        print(f"  ! villages file missing: {VILLAGES_PATH}")
        return

    villages = json.loads(VILLAGES_PATH.read_text(encoding="utf-8"))
    count = 0
    merged = 0
    for v in villages:
        village_id = slugify(v["name"])
        if db.get(Village, village_id):
            continue
        raw_status = (v.get("gram_panchayat_status") or "active").lower()
        if "merged" in raw_status and "uncertain" not in raw_status:
            status = "merged_into_municipal_corporation"
            merged += 1
        elif "uncertain" in raw_status:
            status = "uncertain"
        else:
            status = "active"

        db.add(Village(
            id=village_id, name=v["name"], name_mr=v.get("name_mr") or v["name"],
            lgd_code=v.get("lgd_code"), census_code_2011=v.get("census_code_2011"),
            block_id=HIERARCHY["block"]["id"],
            latitude=v.get("latitude"), longitude=v.get("longitude"),
            population_2011=v.get("population_2011"),
            households_2011=v.get("households_2011"),
            ward_count=9 if village_id == HOME_VILLAGE_ID else 0,
            gram_panchayat_status=status, notes=v.get("notes"),
        ))
        count += 1
    db.commit()
    print(f"Villages: {count} in Haveli taluka ({merged} merged into PMC, no Gram Panchayat)")


def assign_home_village(db: Session) -> None:
    """Point the demo records at Loni Kalbhor.

    Everything seeded from the original mock data belongs to one village; the
    other 22 exist so the district rollup and the village scoping are real
    rather than hypothetical.
    """
    if not db.get(Village, HOME_VILLAGE_ID):
        return
    for model in (Family, Citizen, Grievance, Project, Facility, SabhaMeeting):
        for row in db.query(model).filter(model.village_id.is_(None)).all():
            row.village_id = HOME_VILLAGE_ID
    db.commit()


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
            # Synthetic. Real scheme rules key off these, so without them the
            # engine can only guess — see the note in app/models.py.
            social_category=c.get("social_category"),
            is_bpl=c.get("is_bpl", False),
            secc_listed=c.get("secc_listed", False),
            ration_card_type=c.get("ration_card_type"),
            land_holding_hectares=c.get("land_holding_hectares"),
            marital_status=c.get("marital_status"),
            disability_percent=c.get("disability_percent"),
        ))
        count += 1
    db.commit()
    print(f"Citizens: {count}")


def seed_schemes(db: Session, data: dict) -> None:
    """Load the researched schemes.

    Each record carries its own criteria, required documents, level, category,
    announcement date, and the official URL its figures came from — so every
    number in the system can be traced back to a government page.
    """
    count = 0
    for s in data["schemes"]:
        if db.get(Scheme, s["id"]):
            continue
        db.add(Scheme(
            id=s["id"], name=s["name"], name_mr=s["name_mr"],
            description=s["description"], description_mr=s["description_mr"],
            benefit=s["benefit"], benefit_mr=s["benefit_mr"],
            criteria=s.get("criteria") or {},
            required_documents=s.get("required_documents") or [],
            status=s.get("status", "active"),
            is_government_feed=s.get("is_government_feed", False),
            source_gov=s.get("source_gov"),
            level=s.get("level", "state"),
            category=s.get("category"),
            announced_on=_date(s.get("announced_on")),
            form_url=s.get("form_url"),
            source_url=s.get("source_url"),
            confidence=s.get("confidence", "medium"),
            notes=s.get("notes"),
        ))
        count += 1
    db.commit()

    review = sum(1 for s in data["schemes"] if (s.get("criteria") or {}).get("manual_review"))
    print(f"Schemes: {count} ({review} need officer review — rules a resident record cannot decide)")


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


def seed_grievance_history(db: Session) -> None:
    """Give the seeded complaints a plausible history.

    Without this the citizen tracking view would show a status with no story
    behind it. Each complaint gets its filing event, and anything past Pending
    gets the status change that moved it.
    """
    from datetime import timedelta

    STATUS_MR = {
        "Pending": "प्रलंबित", "In Progress": "प्रगतीपथावर", "Resolved": "निराकरण झाले",
    }
    count = 0
    for g in db.query(Grievance).all():
        if db.query(GrievanceEvent).filter_by(grievance_id=g.id).first():
            continue

        filed_at = datetime.combine(g.submitted_date, datetime.min.time(), timezone.utc)
        db.add(GrievanceEvent(
            id=f"gev_{g.id}_filed", grievance_id=g.id, event_type="filed",
            to_status="Pending",
            note=f"Complaint received and routed to {g.department}",
            note_mr=f"तक्रार प्राप्त झाली असून {g.department_mr} कडे वर्ग करण्यात आली आहे",
            actor_name=g.citizen_name, created_at=filed_at,
        ))
        count += 1

        if g.status != "Pending":
            db.add(GrievanceEvent(
                id=f"gev_{g.id}_progress", grievance_id=g.id,
                event_type="status_changed", from_status="Pending",
                to_status="In Progress",
                note="Site inspection completed; work assigned to the department team.",
                note_mr="स्थळ पाहणी पूर्ण; विभागाच्या पथकाकडे काम सोपवण्यात आले.",
                actor_name="Panchayat Officer",
                created_at=filed_at + timedelta(days=2),
            ))
            count += 1

        if g.status == "Resolved":
            db.add(GrievanceEvent(
                id=f"gev_{g.id}_resolved", grievance_id=g.id,
                event_type="status_changed", from_status="In Progress",
                to_status="Resolved",
                note=g.officer_notes or "Work completed and verified on site.",
                note_mr="काम पूर्ण झाले असून स्थळावर पडताळणी करण्यात आली.",
                actor_name="Panchayat Officer",
                created_at=filed_at + timedelta(days=6),
            ))
            count += 1

    db.commit()
    print(f"Grievance history: {count} events")


# The four original works were recorded as a sanctioned amount and an amount
# spent, with no dates. Their opening entries are dated the first day of the
# financial year the demo is set in, which is what an opening balance is.
OPENING_BALANCE_DATE = date(2026, 4, 1)


def seed_projects(db: Session, data: dict) -> None:
    count = 0
    for p in data["projects"]:
        if db.get(Project, p["id"]):
            continue
        lat, lng = p.get("coordinates") or [0.0, 0.0]
        project = Project(
            id=p["id"], name=p["name"], name_mr=p["nameMr"],
            description=p["description"], description_mr=p["descriptionMr"],
            progress=p["progress"], budget=p["budget"], utilized=p["utilized"],
            status=p["status"], status_mr=p["statusMr"], ward=p["ward"],
            location=p["location"], location_mr=p["locationMr"],
            latitude=lat, longitude=lng,
        )
        db.add(project)
        # Money is held as a ledger now. These works predate it, so each gets
        # the entries that add up to the two totals it was recorded with.
        works.open_ledger(db, project, on=OPENING_BALANCE_DATE)
        count += 1
    db.commit()
    print(f"Projects: {count}")


# The original mock data shipped three documents, none of them an Aadhaar card,
# so no resident could satisfy any scheme's document list and the demo could
# never show an "Eligible" result. `doc_102` also referenced "Amit Shinde", who
# is not in the citizen list at all.
#
# Rather than invent a flat list, these pairs say "this resident has filed a
# complete set for this scheme", and the documents are generated from that
# scheme's own requirements. So the demo always has working examples even when
# the scheme data changes.
COMPLETE_FILES = [
    ("cit_102", "scheme_sanjay_gandhi_niradhar"),   # BPL widow — destitute assistance
    ("cit_102", "scheme_widow_pension"),            # same resident, widow pension
    ("cit_101", "scheme_pm_kisan"),                 # farmer with land
    ("cit_109", "scheme_birsa_munda_krishi_kranti"),# ST farmer, land in band
    ("cit_104", "scheme_ramai_awas"),               # SC household, housing
]

# A few partial files so "Missing Documents" and "Rejected" are visible too.
PARTIAL_FILES = [
    ("cit_105", "Aadhaar Card", "आधार कार्ड", "Rejected", "नाकारले",
     "Photograph is not legible."),
    ("cit_110", "Aadhaar Card", "आधार कार्ड", "Pending Verification", "पडताळणी प्रलंबित", None),
]


def seed_documents(db: Session, data: dict) -> None:
    by_name = {c.name: c for c in db.query(Citizen).all()}
    count = 0

    # Complete, verified sets generated from each scheme's real requirements.
    for citizen_id, scheme_id in COMPLETE_FILES:
        citizen = db.get(Citizen, citizen_id)
        scheme = db.get(Scheme, scheme_id)
        if citizen is None or scheme is None:
            continue
        for i, req in enumerate(scheme.required_documents or [], start=1):
            doc_id = f"doc_{citizen_id}_{scheme_id[7:19]}_{i}"
            if db.get(CitizenDocument, doc_id):
                continue
            slug = "".join(ch for ch in req["name"].lower() if ch.isalnum() or ch == " ")
            path, size = write_sample(
                UPLOAD_ROOT, citizen.id, doc_id, req["name"], citizen.name, "5 August 2026"
            )
            db.add(CitizenDocument(
                id=doc_id, citizen_id=citizen.id,
                doc_type=req["name"], doc_type_mr=req.get("name_mr", req["name"]),
                file_name=f"{slug.replace(' ', '_')}_{citizen_id}.pdf",
                storage_path=str(path), content_type="application/pdf", size_bytes=size,
                status="Verified", status_mr="पडताळणी पूर्ण",
                submitted_date=date(2026, 8, 5),
                verified_at=datetime(2026, 8, 7, tzinfo=timezone.utc),
            ))
            count += 1

    for citizen_id, doc_type, doc_type_mr, st, st_mr, reason in PARTIAL_FILES:
        citizen = db.get(Citizen, citizen_id)
        doc_id = f"doc_partial_{citizen_id}"
        if citizen is None or db.get(CitizenDocument, doc_id):
            continue
        path, size = write_sample(
            UPLOAD_ROOT, citizen.id, doc_id, doc_type, citizen.name, "9 August 2026"
        )
        db.add(CitizenDocument(
            id=doc_id, citizen_id=citizen.id, doc_type=doc_type,
            doc_type_mr=doc_type_mr, file_name=f"aadhaar_{citizen_id}.pdf",
            storage_path=str(path), content_type="application/pdf", size_bytes=size,
            status=st, status_mr=st_mr, submitted_date=date(2026, 8, 9),
            rejection_reason=reason,
        ))
        count += 1

    # Anything still listed in the original mock data.
    for d in data.get("docs", []):
        if db.get(CitizenDocument, d["id"]):
            continue
        citizen = by_name.get(d["citizenName"])
        if citizen is None:
            print(f"  ! skipping {d['id']}: the mock data names {d['citizenName']}, who is not a resident")
            continue
        path, size = write_sample(
            UPLOAD_ROOT, citizen.id, d["id"], d["docType"], citizen.name,
            d.get("submittedDate", "")[:10] or "9 August 2026",
        )
        db.add(CitizenDocument(
            id=d["id"], citizen_id=citizen.id,
            doc_type=d["docType"], doc_type_mr=d["docTypeMr"],
            file_name=d["fileName"], status=d["status"], status_mr=d["statusMr"],
            storage_path=str(path), content_type="application/pdf", size_bytes=size,
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


# Residents deliberately left without a portal account. In a real village most
# residents would not have signed up yet, and the registration queue needs
# somebody an officer can actually approve.
UNREGISTERED_CITIZEN_IDS = {"cit_109", "cit_110"}


def seed_users(db: Session) -> None:
    password = hash_password(settings.SEED_DEFAULT_PASSWORD)
    created = 0

    for user_id, email, name, role in [
        ("usr_admin", "admin@panchayat.gov.in", "System Administrator", "admin"),
        ("usr_officer", "officer@panchayat.gov.in", "Panchayat Officer", "officer"),
    ]:
        if db.get(User, user_id):
            continue
        db.add(User(
            id=user_id, email=email, hashed_password=password,
            full_name=name, role=role,
            # An admin has no village and sees the whole district.
            village_id=None if role == "admin" else HOME_VILLAGE_ID,
        ))
        created += 1

    # One login per citizen, so the portal can be demonstrated as that person —
    # except the residents held back above, who are on the village register with
    # no account yet. Somebody has to be in that position or the sign-up flow
    # cannot be shown at all: an officer approving an application has to have an
    # unclaimed record to attach it to.
    for citizen in db.query(Citizen).all():
        if citizen.id in UNREGISTERED_CITIZEN_IDS:
            continue
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
            village_id=citizen.village_id,
        ))
        created += 1

    db.commit()
    print(f"Users: {created}")


def seed_neighbour_officer(db: Session) -> None:
    """An officer in a neighbouring village.

    Exists so village scoping can be demonstrated rather than asserted: sign in
    as this account and the resident list is empty, because Theur has no seeded
    residents and this officer cannot see Loni Kalbhor's.
    """
    neighbour = db.get(Village, "vil_theur")
    if neighbour is None or db.get(User, "usr_officer_theur"):
        return
    db.add(User(
        id="usr_officer_theur", email="officer.theur@panchayat.gov.in",
        hashed_password=hash_password(settings.SEED_DEFAULT_PASSWORD),
        full_name="Theur Panchayat Officer", role="officer",
        village_id=neighbour.id,
    ))
    db.commit()
    print("Neighbouring officer: officer.theur@panchayat.gov.in (Theur)")


# ─────────────────────────────────────────────────────────────────────────────
# The works demo
#
# Three situations a Panchayat is always in at once, so that the path from a
# complaint to a finished work can be shown without first spending ten minutes
# filing things:
#
#   A  a work in mid-flight — twenty streetlights asked for by five residents,
#      sanctioned for less than was requested, fourteen installed so far
#   B  a proposal the Panchayat approved and then heard nothing about — the
#      budget was requested eleven weeks ago
#   C  three complaints about the same thing that nobody has acted on yet,
#      waiting to be turned into a proposal
#
# Nothing below writes a stage, a total or a priority directly. Each complaint
# is classified and ranked by the same rules the API applies, and each work is
# walked through `services.works` one step at a time with the clock set to the
# day that step is meant to have happened. So what is in the database is what
# the system would have recorded had somebody really done all this — which is
# the only honest way to have demo data for rules that are supposed to be
# enforced.
#
# Dates are counted back from the day this runs, not fixed, because half of what
# it shows is about elapsed time. `--refresh-works-demo` rebuilds it around
# today.
#
# Every row has an id starting `grv_demo_` or `proj_demo_`, and that is how
# `remove_works_demo` finds them again.
# ─────────────────────────────────────────────────────────────────────────────

WORKS_DEMO_GRIEVANCES = "grv_demo_"
WORKS_DEMO_PROJECTS = "proj_demo_"


def _demo_complaint(
    db: Session,
    officer: User,
    *,
    id: str,
    day: date,
    ward: int,
    title: str,
    title_mr: str,
    description: str,
    description_mr: str,
    citizen_id: str | None = None,
    walk_in: str | None = None,
) -> Grievance:
    """File one complaint as it would have been filed on `day`.

    `citizen_id` for a resident using their own login; `walk_in` for someone
    who came to the office and had an officer write it down, which the API
    records with a name and no resident behind it.
    """
    result = classify(title, description)
    citizen = db.get(Citizen, citizen_id) if citizen_id else None
    filer = db.get(User, f"usr_{citizen_id}") if citizen_id else officer

    with clock.at(day):
        grievance = Grievance(
            id=id, title=title, title_mr=title_mr,
            description=description, description_mr=description_mr,
            category=result.category, category_mr=result.category_mr,
            priority=result.priority, priority_mr=result.priority_mr,
            status="Pending", status_mr="प्रलंबित",
            department=result.department, department_mr=result.department_mr,
            # No coordinates. Neither filing form sends any, so a complaint that
            # really came through the portal has none, and the map says how many
            # it cannot place rather than showing pins nobody put there.
            ward=ward,
            citizen_id=citizen.id if citizen else None,
            citizen_name=citizen.name if citizen else (walk_in or "Walk-in complainant"),
            submitted_date=day, auto_classified=True,
            village_id=HOME_VILLAGE_ID,
            request_type=result.request_type,
            requested_quantity=result.requested_quantity,
            created_at=clock.now(),
        )
        db.add(grievance)
        db.flush()
        timeline.grievance_event(
            db, grievance, "filed", filer, to_status="Pending",
            note=f"Complaint received and routed to {grievance.department}",
            note_mr=f"तक्रार प्राप्त झाली असून {grievance.department_mr} कडे वर्ग करण्यात आली आहे",
            actor_name=grievance.citizen_name,
        )
        # The same call the API makes: more residents reporting one problem
        # raises it for all of them.
        demand.apply_demand(db, grievance)
        db.flush()
    return grievance


def seed_works_demo(db: Session, today: date | None = None) -> None:
    if db.get(Project, f"{WORKS_DEMO_PROJECTS}streetlights"):
        print("Works demo: already present")
        return
    officer = db.get(User, "usr_officer")
    if officer is None or db.get(Village, HOME_VILLAGE_ID) is None:
        print("Works demo: skipped — it needs the home village and its officer")
        return

    today = today or date.today()

    def ago(days: int) -> date:
        return today - timedelta(days=days)

    # ── A. Twenty streetlights, Ward 2 ───────────────────────────────────────
    lights = [
        _demo_complaint(
            db, officer, id=f"{WORKS_DEMO_GRIEVANCES}light_1", day=ago(94), ward=2,
            citizen_id="cit_101",
            title="Need 20 more streetlights from Market Road to the Vitthal temple",
            title_mr="बाजार रस्ता ते विठ्ठल मंदिर या मार्गावर आणखी २० पथदिवे हवेत",
            description=(
                "The stretch from Market Road to the Vitthal temple has only four poles "
                "and stays dark after sunset. Please install 20 additional streetlights "
                "along it."
            ),
            description_mr=(
                "बाजार रस्त्यापासून विठ्ठल मंदिरापर्यंतच्या मार्गावर फक्त चार खांब आहेत आणि "
                "सूर्यास्तानंतर पूर्ण अंधार असतो. या मार्गावर आणखी २० पथदिवे बसवावेत."
            ),
        ),
        _demo_complaint(
            db, officer, id=f"{WORKS_DEMO_GRIEVANCES}light_2", day=ago(93), ward=2,
            citizen_id="cit_102",
            title="Streetlights needed between the market and the temple",
            title_mr="बाजार ते मंदिर या दरम्यान पथदिवे हवेत",
            description=(
                "Women coming back from the market in the evening walk this stretch in "
                "complete darkness. More streetlights should be installed here."
            ),
            description_mr=(
                "संध्याकाळी बाजारातून परतणाऱ्या महिलांना या मार्गावरून पूर्ण अंधारात चालावे "
                "लागते. येथे आणखी पथदिवे बसवावेत."
            ),
        ),
        _demo_complaint(
            db, officer, id=f"{WORKS_DEMO_GRIEVANCES}light_3", day=ago(91), ward=2,
            citizen_id="cit_103",
            title="Additional streetlight poles required on the temple stretch",
            title_mr="मंदिर मार्गावर अतिरिक्त पथदिव्यांचे खांब हवेत",
            description=(
                "There are only four poles on this whole stretch. Install additional "
                "streetlight poles so that the entire way is lit."
            ),
            description_mr=(
                "या संपूर्ण मार्गावर फक्त चार खांब आहेत. संपूर्ण मार्ग उजळेल असे अतिरिक्त "
                "पथदिव्यांचे खांब बसवावेत."
            ),
        ),
        _demo_complaint(
            db, officer, id=f"{WORKS_DEMO_GRIEVANCES}light_4", day=ago(89), ward=2,
            walk_in="Mangal Kamble",
            title="Install new streetlights on the market to temple way",
            title_mr="बाजार ते मंदिर मार्गावर नवीन पथदिवे बसवावेत",
            description=(
                "Recorded at the Panchayat office counter. The way is dark after seven "
                "in the evening and new streetlights are asked for."
            ),
            description_mr=(
                "पंचायत कार्यालयात नोंदवलेली मागणी. संध्याकाळी सातनंतर मार्गावर अंधार असतो; "
                "नवीन पथदिवे बसवण्याची मागणी आहे."
            ),
        ),
        _demo_complaint(
            db, officer, id=f"{WORKS_DEMO_GRIEVANCES}light_5", day=ago(87), ward=2,
            walk_in="Dattatray Bhosale",
            title="More streetlights needed, market to temple",
            title_mr="बाजार ते मंदिर मार्गावर आणखी पथदिवे हवेत",
            description=(
                "Shopkeepers close early because customers avoid the dark stretch. Need "
                "20 streetlights installed here, as the others have asked."
            ),
            description_mr=(
                "अंधारामुळे ग्राहक या मार्गावर येत नाहीत, त्यामुळे दुकानदार लवकर दुकाने बंद "
                "करतात. इतरांनी मागितल्याप्रमाणे येथे २० पथदिवे बसवावेत."
            ),
        ),
    ]

    with clock.at(ago(86)):
        streetlights = works.propose(
            db, officer,
            id=f"{WORKS_DEMO_PROJECTS}streetlights", village_id=HOME_VILLAGE_ID,
            name="20 Streetlights — Market Road to Vitthal Temple",
            name_mr="२० पथदिवे — बाजार रस्ता ते विठ्ठल मंदिर",
            description=(
                "Twenty streetlights on the stretch between Market Road and the Vitthal "
                "temple, which has four working lights. Asked for by residents of Ward 2."
            ),
            description_mr=(
                "बाजार रस्ता ते विठ्ठल मंदिर या मार्गावर वीस पथदिवे. सध्या या मार्गावर फक्त "
                "चार दिवे सुरू आहेत. प्रभाग २ मधील रहिवाशांची मागणी."
            ),
            ward=2, location="Ward 2, Market Road to Vitthal Temple",
            location_mr="प्रभाग २, बाजार रस्ता ते विठ्ठल मंदिर",
            latitude=18.4889, longitude=74.0211, category="Electricity",
            units_planned=20, unit_label="streetlights", unit_label_mr="पथदिवे",
            asset_type="streetlight", expected_completion=today + timedelta(days=27),
            created_at=clock.now(),
        )
        works.link_grievances(db, streetlights, lights, officer)

    with clock.at(ago(80)):
        works.act(
            db, streetlights, "verify", officer,
            note=(
                "Site visit with the ward member. The stretch is about 600 m and has "
                "four working lights; twenty poles are needed to light it end to end."
            ),
        )
        works.add_entry(
            db, streetlights, officer, kind="estimate", amount=400_000,
            note="Poles, fittings, cabling and labour for twenty lights.",
        )

    # Approved at the Gram Sabha, if the seeded meeting happens to fall between
    # the field check and the budget request. It does when this runs in the
    # weeks the demo is set in; on a later run the decision is simply dated.
    approved_on = ago(61)
    meeting = db.get(SabhaMeeting, "sabha_401")
    in_sabha = (
        meeting is not None
        and meeting.village_id == HOME_VILLAGE_ID
        and ago(80) < meeting.meeting_date < ago(59)
    )
    if in_sabha:
        approved_on = meeting.meeting_date
    with clock.at(approved_on):
        works.act(
            db, streetlights, "approve", officer,
            note=(
                "Approved in the Gram Sabha. To be taken up from the Finance Commission grant."
                if in_sabha
                else "Approved by the Panchayat. To be taken up from the Finance Commission grant."
            ),
            sabha_meeting_id=meeting.id if in_sabha else None,
        )

    with clock.at(ago(59)):
        works.add_entry(
            db, streetlights, officer, kind="requested", amount=400_000,
            funding_source="cfc", reference=f"LK/GP/{works.financial_year(ago(59))}/41",
            note="Proposal sent to the Panchayat Samiti.",
        )
    with clock.at(ago(40)):
        works.add_entry(
            db, streetlights, officer, kind="approved", amount=350_000,
            funding_source="cfc", reference=f"PS-HVL/FC/{works.financial_year(ago(40))}/212",
            note="Sanction order received.",
        )
    with clock.at(ago(29)):
        works.add_entry(
            db, streetlights, officer, kind="received", amount=350_000,
            funding_source="cfc", note="Credited to the Panchayat account.",
        )
    with clock.at(ago(24)):
        works.act(db, streetlights, "start", officer, note="Work order issued.")
    with clock.at(ago(16)):
        works.add_entry(
            db, streetlights, officer, kind="spent", amount=160_000,
            reference="Bill 0147", note="Poles and light fittings supplied.",
        )
        works.record_progress(
            db, streetlights, officer, units_done=8, note="First eight poles erected and lit.",
        )
    with clock.at(ago(6)):
        works.add_entry(
            db, streetlights, officer, kind="spent", amount=120_000,
            reference="Bill 0163", note="Cabling and installation labour.",
        )
        works.record_progress(db, streetlights, officer, units_done=14)

    # ── B. Three tap stands, Ward 4 — approved, budget asked for, no answer ──
    tap_requests = [
        _demo_complaint(
            db, officer, id=f"{WORKS_DEMO_GRIEVANCES}tap_1", day=ago(110), ward=4,
            citizen_id="cit_104",
            title="Need 3 new public water taps in Shinde Vasti",
            title_mr="शिंदे वस्तीत ३ नवीन सार्वजनिक नळ हवेत",
            description=(
                "About forty households share a single tap stand. Please install 3 new "
                "public taps so that the morning queue is shorter."
            ),
            description_mr=(
                "सुमारे चाळीस कुटुंबांना एकाच नळ कोंडाळ्यावर अवलंबून राहावे लागते. सकाळची "
                "रांग कमी व्हावी म्हणून ३ नवीन सार्वजनिक नळ बसवावेत."
            ),
        ),
        _demo_complaint(
            db, officer, id=f"{WORKS_DEMO_GRIEVANCES}tap_2", day=ago(104), ward=4,
            citizen_id="cit_105",
            title="More drinking water taps required for our vasti",
            title_mr="आमच्या वस्तीसाठी पिण्याच्या पाण्याचे आणखी नळ हवेत",
            description=(
                "There is one tap for the whole vasti. Additional taps should be "
                "installed near the temple end."
            ),
            description_mr=(
                "संपूर्ण वस्तीसाठी एकच नळ आहे. मंदिराच्या बाजूला अतिरिक्त नळ बसवावेत."
            ),
        ),
    ]

    with clock.at(ago(100)):
        taps = works.propose(
            db, officer,
            id=f"{WORKS_DEMO_PROJECTS}taps", village_id=HOME_VILLAGE_ID,
            name="3 Public Water Tap Stands — Shinde Vasti",
            name_mr="३ सार्वजनिक नळ कोंडाळी — शिंदे वस्ती",
            description=(
                "Three public tap stands for Shinde Vasti, where about forty households "
                "share one."
            ),
            description_mr=(
                "शिंदे वस्तीसाठी तीन सार्वजनिक नळ कोंडाळी. सध्या सुमारे चाळीस कुटुंबे एकाच "
                "नळावर अवलंबून आहेत."
            ),
            ward=4, location="Ward 4, Shinde Vasti", location_mr="प्रभाग ४, शिंदे वस्ती",
            latitude=18.4902, longitude=74.0244, category="Water",
            units_planned=3, unit_label="tap stands", unit_label_mr="नळ कोंडाळी",
            asset_type="water", created_at=clock.now(),
        )
        works.link_grievances(db, taps, tap_requests, officer)
    with clock.at(ago(95)):
        works.act(
            db, taps, "verify", officer,
            note=(
                "Visited in the morning. One tap stand serves the whole settlement and "
                "the queue runs past the temple; three more are justified."
            ),
        )
        works.add_entry(
            db, taps, officer, kind="estimate", amount=180_000,
            note="Three stand posts with platform and connection to the existing main.",
        )
    with clock.at(ago(88)):
        works.act(db, taps, "approve", officer, note="Approved by the Panchayat.")
    with clock.at(ago(76)):
        works.add_entry(
            db, taps, officer, kind="requested", amount=180_000, funding_source="zp",
            reference=f"LK/GP/{works.financial_year(ago(76))}/37",
            note="Proposal sent to the Panchayat Samiti.",
        )

    # ── C. Three complaints, Ward 3, that nobody has acted on yet ────────────
    _demo_complaint(
        db, officer, id=f"{WORKS_DEMO_GRIEVANCES}bin_1", day=ago(9), ward=3,
        citizen_id="cit_106",
        title="Request for 8 garbage bins along Deshmukh Ali",
        title_mr="देशमुख आळीत ८ कचराकुंड्यांची मागणी",
        description=(
            "Household waste is left at the corner because there is nowhere to put it. "
            "We would like 8 garbage bins installed along the ali."
        ),
        description_mr=(
            "कचरा टाकायला जागा नसल्याने घरातील कचरा कोपऱ्यावर टाकला जातो. आळीत ८ "
            "कचराकुंड्या बसवाव्यात."
        ),
    )
    _demo_complaint(
        db, officer, id=f"{WORKS_DEMO_GRIEVANCES}bin_2", day=ago(7), ward=3,
        citizen_id="cit_107",
        title="Request to install garbage bins near the temple square",
        title_mr="मंदिर चौकाजवळ कचराकुंड्या बसवण्याची विनंती",
        description=(
            "There is no bin anywhere in this part of the ward, so garbage piles up in "
            "the open. We suggest new bins be installed."
        ),
        description_mr=(
            "प्रभागाच्या या भागात कुठेही कचराकुंडी नाही, त्यामुळे कचरा उघड्यावर साचतो. "
            "नवीन कचराकुंड्या बसवाव्यात."
        ),
    )
    _demo_complaint(
        db, officer, id=f"{WORKS_DEMO_GRIEVANCES}bin_3", day=ago(4), ward=3,
        walk_in="Sunil Ghadge",
        title="Suggest additional garbage bins for Ward 3",
        title_mr="प्रभाग ३ साठी अतिरिक्त कचराकुंड्या",
        description=(
            "Recorded at the Panchayat office counter. Garbage is dumped beside the open "
            "plot because there are no bins. Additional bins would help."
        ),
        description_mr=(
            "पंचायत कार्यालयात नोंदवलेली मागणी. कचराकुंड्या नसल्याने मोकळ्या जागेशेजारी "
            "कचरा टाकला जातो. अतिरिक्त कचराकुंड्या हव्यात."
        ),
    )

    db.commit()
    print(
        "Works demo: 10 complaints and 2 works — streetlights in progress (ward 2), "
        "tap stands awaiting budget (ward 4), bins not yet taken up (ward 3)"
    )


def remove_works_demo(db: Session) -> None:
    """Take the demo out again, along with anything it grew.

    A demo work that was completed during a walkthrough has added a row to the
    asset register, and the index the assistant searches may hold a chunk for
    each record. Those go too. A real complaint that somebody linked to a demo
    work by hand is kept; it just stops pointing at a work that is about to
    disappear.
    """
    projects = list(db.scalars(
        select(Project).where(Project.id.startswith(WORKS_DEMO_PROJECTS, autoescape=True))
    ))
    grievances = list(db.scalars(
        select(Grievance).where(Grievance.id.startswith(WORKS_DEMO_GRIEVANCES, autoescape=True))
    ))
    if not projects and not grievances:
        print("Works demo: nothing to remove")
        return

    project_ids = [p.id for p in projects]
    facilities = list(db.scalars(
        select(Facility).where(Facility.project_id.in_(project_ids))
    )) if project_ids else []

    gone = {*project_ids, *(g.id for g in grievances), *(f.id for f in facilities)}
    demo_grievance_ids = {g.id for g in grievances}
    if project_ids:
        for grievance in db.scalars(
            select(Grievance).where(Grievance.project_id.in_(project_ids))
        ):
            if grievance.id not in demo_grievance_ids:
                grievance.project_id = None
        db.flush()

    db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.entity_id.in_(gone)))
    for row in (*facilities, *grievances, *projects):
        db.delete(row)
    db.commit()
    print(
        f"Works demo: removed {len(grievances)} complaints, {len(projects)} works "
        f"and {len(facilities)} asset(s)"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the E-Panchayat database.")
    parser.add_argument("--reset", action="store_true",
                        help="delete all existing rows before seeding")
    parser.add_argument("--create-tables", action="store_true",
                        help="create tables directly instead of running Alembic")
    parser.add_argument("--refresh-works-demo", action="store_true",
                        help="remove the works demo and build it again, dated from today")
    parser.add_argument("--remove-works-demo", action="store_true",
                        help="remove the works demo and do nothing else")
    args = parser.parse_args()

    if args.remove_works_demo:
        with SessionLocal() as db:
            remove_works_demo(db)
        return

    if args.create_tables:
        Base.metadata.create_all(engine)
        print("Tables created.")

    data = load_data()
    with SessionLocal() as db:
        if args.reset:
            reset(db)
        seed_hierarchy(db)
        seed_villages(db)
        seed_families(db, data)
        seed_citizens(db, data)
        seed_schemes(db, data)
        seed_grievances(db, data)
        seed_grievance_history(db)
        seed_projects(db, data)
        seed_documents(db, data)
        seed_sabha(db, data)
        seed_facilities(db, data)
        assign_home_village(db)
        seed_users(db)
        seed_neighbour_officer(db)
        if args.refresh_works_demo:
            remove_works_demo(db)
        seed_works_demo(db)

    print(f"\nDone. Sign in as officer@panchayat.gov.in / {settings.SEED_DEFAULT_PASSWORD}")


if __name__ == "__main__":
    main()
