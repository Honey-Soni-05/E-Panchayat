"""Welfare schemes, the government scheme feed, and the eligibility engine."""

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import assert_can_read_citizen, get_current_user, require_officer
from app.db.session import get_db
from app.models import Citizen, CitizenDocument, Scheme, User
from app.schemas import (
    DocumentGap,
    EligibilityResult,
    SchemeCreate,
    SchemeOut,
    SchemeUpdate,
)
from app.services import eligibility as elig

router = APIRouter(tags=["schemes"])


def _result(a: elig.Assessment, language: str) -> EligibilityResult:
    return EligibilityResult(
        citizen_id=a.citizen.id,
        citizen_name=a.citizen.name,
        citizen_name_mr=a.citizen.name_mr,
        ward=a.citizen.ward,
        scheme_id=a.scheme.id,
        status=a.status,
        status_mr=elig.STATUS_MR[a.status],
        criteria_passed=a.criteria_passed,
        failed_criteria=a.failed_criteria_mr if language == "mr" else a.failed_criteria,
        missing_documents=[
            DocumentGap(name=d.name, name_mr=d.name_mr) for d in a.missing_documents
        ],
        unverified_documents=[
            DocumentGap(name=d.name, name_mr=d.name_mr, file_status=d.file_status)
            for d in a.unverified_documents
        ],
        explanation=elig.explain(a, "en"),
        explanation_mr=elig.explain(a, "mr"),
    )


@router.get("/schemes", response_model=list[SchemeOut])
def list_schemes(
    include_feed: bool = Query(False, description="Include unapproved government feed items"),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Scheme]:
    stmt = select(Scheme)
    if not include_feed:
        stmt = stmt.where(Scheme.status == "active")
    return list(db.scalars(stmt.order_by(Scheme.name)))


@router.get("/schemes/feed", response_model=list[SchemeOut])
def scheme_feed(
    _: User = Depends(require_officer), db: Session = Depends(get_db)
) -> list[Scheme]:
    """Schemes published by the state that this Panchayat has not yet adopted."""
    stmt = select(Scheme).where(
        Scheme.is_government_feed.is_(True), Scheme.status == "pending"
    )
    return list(db.scalars(stmt.order_by(Scheme.name)))


@router.post("/schemes", response_model=SchemeOut, status_code=status.HTTP_201_CREATED)
def create_scheme(
    body: SchemeCreate,
    _: User = Depends(require_officer),
    db: Session = Depends(get_db),
) -> Scheme:
    scheme_id = body.id or f"scheme_{uuid4().hex[:10]}"
    if db.get(Scheme, scheme_id):
        raise HTTPException(status.HTTP_409_CONFLICT, "That scheme ID is already in use.")

    data = body.model_dump(exclude={"id"})
    data["required_documents"] = [
        {"name": d["name"], "name_mr": d["name_mr"]} for d in data["required_documents"]
    ]
    scheme = Scheme(id=scheme_id, **data)
    db.add(scheme)
    db.commit()
    db.refresh(scheme)
    return scheme


@router.patch("/schemes/{scheme_id}", response_model=SchemeOut)
def update_scheme(
    scheme_id: str,
    body: SchemeUpdate,
    _: User = Depends(require_officer),
    db: Session = Depends(get_db),
) -> Scheme:
    scheme = db.get(Scheme, scheme_id)
    if scheme is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No scheme with that ID.")

    for field, value in body.model_dump(exclude_unset=True).items():
        if field == "required_documents" and value is not None:
            value = [{"name": d["name"], "name_mr": d["name_mr"]} for d in value]
        setattr(scheme, field, value)
    db.commit()
    db.refresh(scheme)
    return scheme


@router.post("/schemes/{scheme_id}/decision", response_model=SchemeOut)
def decide_feed_scheme(
    scheme_id: str,
    approve: bool = Query(..., description="true adopts the scheme, false rejects it"),
    _: User = Depends(require_officer),
    db: Session = Depends(get_db),
) -> Scheme:
    """Adopt or reject a scheme from the government feed."""
    scheme = db.get(Scheme, scheme_id)
    if scheme is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No scheme with that ID.")
    scheme.status = "active" if approve else "rejected"
    db.commit()
    db.refresh(scheme)
    return scheme


@router.get("/schemes/{scheme_id}/eligibility", response_model=list[EligibilityResult])
def scheme_eligibility(
    scheme_id: str,
    ward: int | None = None,
    only: str | None = Query(
        None, description="Filter to 'Eligible', 'Missing Documents' or 'Ineligible'"
    ),
    language: str = Query("en", pattern="^(en|mr)$"),
    _: User = Depends(require_officer),
    db: Session = Depends(get_db),
) -> list[EligibilityResult]:
    """Assess every citizen against one scheme. This is the beneficiary
    recommendation screen's data source."""
    scheme = db.get(Scheme, scheme_id)
    if scheme is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No scheme with that ID.")

    stmt = select(Citizen).options(selectinload(Citizen.documents))
    if ward is not None:
        stmt = stmt.where(Citizen.ward == ward)

    results = [
        _result(elig.assess(c, scheme, list(c.documents)), language)
        for c in db.scalars(stmt.order_by(Citizen.ward, Citizen.name))
    ]
    if only:
        results = [r for r in results if r.status == only]

    # Eligible first, then near-misses, then the rest — the order an officer works in.
    rank = {"Eligible": 0, "Missing Documents": 1, "Ineligible": 2}
    results.sort(key=lambda r: (rank.get(r.status, 3), r.ward, r.citizen_name))
    return results


@router.get("/citizens/{citizen_id}/eligibility", response_model=list[EligibilityResult])
def citizen_eligibility(
    citizen_id: str,
    language: str = Query("en", pattern="^(en|mr)$"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[EligibilityResult]:
    """Every active scheme assessed for one citizen — the citizen portal view."""
    assert_can_read_citizen(user, citizen_id)

    citizen = db.get(Citizen, citizen_id)
    if citizen is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No citizen with that ID.")

    docs = list(db.scalars(
        select(CitizenDocument).where(CitizenDocument.citizen_id == citizen_id)
    ))
    schemes = db.scalars(select(Scheme).where(Scheme.status == "active"))

    results = [_result(elig.assess(citizen, s, docs), language) for s in schemes]
    rank = {"Eligible": 0, "Missing Documents": 1, "Ineligible": 2}
    results.sort(key=lambda r: rank.get(r.status, 3))
    return results
