"""Welfare schemes, the government scheme feed, and the eligibility engine."""

from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
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
    SchemeReadResult,
    SchemeUpdate,
)
from app.services import eligibility as elig
from app.services.llm import LLMUnavailable
from app.services.scheme_reader import SchemeExtractionError, read_scheme
from app.services.transcript import UnsupportedTranscript, extract_text

router = APIRouter(tags=["schemes"])


def _result(a: elig.Assessment, language: str) -> EligibilityResult:
    return EligibilityResult(
        citizen_id=a.citizen.id,
        citizen_name=a.citizen.name,
        citizen_name_mr=a.citizen.name_mr,
        ward=a.citizen.ward,
        scheme_id=a.scheme.id,
        scheme_name=a.scheme.name,
        scheme_name_mr=a.scheme.name_mr,
        status=a.status,
        status_mr=elig.STATUS_MR[a.status],
        criteria_passed=a.criteria_passed,
        unknown_attributes=a.unknown_attributes,
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


MAX_GR_UPLOAD = 8 * 1024 * 1024


@router.post(
    "/schemes/read",
    response_model=SchemeReadResult,
    status_code=status.HTTP_201_CREATED,
)
async def read_scheme_document(
    file: UploadFile = File(...),
    officer: User = Depends(require_officer),
    db: Session = Depends(get_db),
) -> SchemeReadResult:
    """Read a Government Resolution and propose a scheme from it.

    The proposal is saved with status 'pending', which keeps it out of every
    citizen-facing list and out of the eligibility engine until an officer
    approves it through /schemes/{id}/decision. Nothing a model extracted tells
    a resident they qualify for anything before a person has checked it against
    the GR.
    """
    payload = await file.read()
    if len(payload) > MAX_GR_UPLOAD:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"That file is {len(payload) / 1_048_576:.1f} MB. The limit is 8 MB.",
        )

    try:
        text = extract_text(file.filename or "", payload)
    except UnsupportedTranscript as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    try:
        draft = await read_scheme(text, source_name=file.filename)
    except SchemeExtractionError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except LLMUnavailable as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"{exc} Add the scheme by hand, or set GEMINI_API_KEY on the server.",
        ) from exc

    review = draft.pop("_review")
    scheme = Scheme(
        id=f"scheme_gr_{uuid4().hex[:10]}",
        status="pending",
        is_government_feed=True,
        source_gov=f"Uploaded by {officer.full_name}",
        **draft,
    )
    db.add(scheme)
    db.commit()
    db.refresh(scheme)

    return SchemeReadResult(
        scheme=SchemeOut.model_validate(scheme, from_attributes=True),
        unmappable_conditions=review["unmappable_conditions"],
        discarded_criteria=review["discarded_criteria"],
        confidence_note=review["confidence_note"],
        needs_manual_review=review["needs_manual_review"],
    )


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
    rank = {s: i for i, s in enumerate(elig.STATUS_ORDER)}
    results.sort(key=lambda r: (rank.get(r.status, 9), r.ward, r.citizen_name))
    return results


@router.get("/citizens/{citizen_id}/eligibility", response_model=list[EligibilityResult])
def citizen_eligibility(
    citizen_id: str,
    language: str = Query("en", pattern="^(en|mr)$"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[EligibilityResult]:
    """Every active scheme assessed for one citizen — the citizen portal view."""
    assert_can_read_citizen(db, user, citizen_id)

    citizen = db.get(Citizen, citizen_id)
    if citizen is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No citizen with that ID.")

    docs = list(db.scalars(
        select(CitizenDocument).where(CitizenDocument.citizen_id == citizen_id)
    ))
    schemes = db.scalars(select(Scheme).where(Scheme.status == "active"))

    results = [_result(elig.assess(citizen, s, docs), language) for s in schemes]
    rank = {s: i for i, s in enumerate(elig.STATUS_ORDER)}
    results.sort(key=lambda r: rank.get(r.status, 9))
    return results
