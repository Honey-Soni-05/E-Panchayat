"""Grievance registration, classification and resolution workflow."""

from datetime import date
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import get_current_user, require_officer, village_scope
from app.db.session import get_db
from app.models import Citizen, Grievance, GrievanceEvent, User
from app.schemas import (
    GrievanceCreate,
    GrievanceDetail,
    GrievanceOut,
    GrievanceUpdate,
)
from app.services.classifier import PRIORITY_MR, classify

router = APIRouter(prefix="/grievances", tags=["grievances"])

STATUS_MR = {"Pending": "प्रलंबित", "In Progress": "प्रगतीपथावर", "Resolved": "निराकरण झाले"}

# The three stages a complaint moves through, in order. The citizen tracking
# view renders this as a progress bar, so the order matters.
STATUS_SEQUENCE = ["Pending", "In Progress", "Resolved"]


def log_event(
    db: Session,
    grievance: Grievance,
    event_type: str,
    actor: User | None,
    *,
    from_status: str | None = None,
    to_status: str | None = None,
    note: str | None = None,
    note_mr: str | None = None,
) -> None:
    """Record one step in a complaint's history.

    Every change goes through here, so the timeline a citizen sees is the
    actual record of what happened rather than something reconstructed from
    the current state.
    """
    db.add(GrievanceEvent(
        id=f"gev_{uuid4().hex[:12]}",
        grievance_id=grievance.id,
        event_type=event_type,
        from_status=from_status,
        to_status=to_status,
        note=note,
        note_mr=note_mr,
        actor_id=actor.id if actor else None,
        actor_name=actor.full_name if actor else None,
    ))


@router.get("", response_model=list[GrievanceOut])
def list_grievances(
    status_filter: str | None = Query(None, alias="status"),
    category: str | None = None,
    priority: str | None = None,
    ward: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Grievance]:
    stmt = select(Grievance)

    # A citizen sees only the complaints they filed.
    if user.role == "citizen":
        if not user.citizen_id:
            return []
        stmt = stmt.where(Grievance.citizen_id == user.citizen_id)

    else:
        scope = village_scope(user)
        if scope is not None:
            stmt = stmt.where(Grievance.village_id == scope)

    if status_filter:
        stmt = stmt.where(Grievance.status == status_filter)
    if category:
        stmt = stmt.where(Grievance.category == category)
    if priority:
        stmt = stmt.where(Grievance.priority == priority)
    if ward is not None:
        stmt = stmt.where(Grievance.ward == ward)

    return list(db.scalars(stmt.order_by(Grievance.submitted_date.desc())))


@router.post("", response_model=GrievanceOut, status_code=status.HTTP_201_CREATED)
def create_grievance(
    body: GrievanceCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Grievance:
    """Anyone signed in may file. Category, priority and routing department are
    assigned by the classifier unless an officer supplies them explicitly."""
    result = classify(body.title, body.description)

    citizen: Citizen | None = None
    if user.role == "citizen" and user.citizen_id:
        citizen = db.get(Citizen, user.citizen_id)

    citizen_name = body.citizen_name or (citizen.name if citizen else user.full_name)
    overridden = bool(body.category or body.priority)

    grievance = Grievance(
        id=f"griev_{uuid4().hex[:10]}",
        title=body.title,
        title_mr=body.title_mr or body.title,
        description=body.description,
        description_mr=body.description_mr or body.description,
        category=body.category or result.category,
        category_mr=result.category_mr,
        priority=body.priority or result.priority,
        priority_mr=PRIORITY_MR.get(body.priority or result.priority, result.priority_mr),
        status="Pending",
        status_mr=STATUS_MR["Pending"],
        department=result.department,
        department_mr=result.department_mr,
        ward=body.ward,
        latitude=body.latitude,
        longitude=body.longitude,
        citizen_id=citizen.id if citizen else None,
        citizen_name=citizen_name,
        phone=body.phone or (citizen.phone if citizen else None),
        submitted_date=date.today(),
        auto_classified=not overridden,
        # A complaint belongs to the filer's village, or the officer's.
        village_id=(citizen.village_id if citizen else None) or village_scope(user),
    )
    db.add(grievance)
    db.flush()
    log_event(
        db, grievance, "filed", user,
        to_status="Pending",
        note="Complaint received and routed to " + grievance.department,
        note_mr="तक्रार प्राप्त झाली असून " + grievance.department_mr + " कडे वर्ग करण्यात आली आहे",
    )
    db.commit()
    db.refresh(grievance)
    return grievance


@router.get("/{grievance_id}", response_model=GrievanceDetail)
def get_grievance(
    grievance_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Grievance:
    grievance = db.scalar(
        select(Grievance)
        .options(selectinload(Grievance.events))
        .where(Grievance.id == grievance_id)
    )
    if grievance is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No grievance with that ID.")
    if user.role == "citizen" and grievance.citizen_id != user.citizen_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only view your own complaints.")
    return grievance


@router.patch("/{grievance_id}", response_model=GrievanceOut)
def update_grievance(
    grievance_id: str,
    body: GrievanceUpdate,
    officer: User = Depends(require_officer),
    db: Session = Depends(get_db),
) -> Grievance:
    grievance = db.get(Grievance, grievance_id)
    if grievance is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No grievance with that ID.")

    data = body.model_dump(exclude_unset=True)
    note = data.get("officer_notes")

    if (new_status := data.get("status")) is not None and new_status != grievance.status:
        previous = grievance.status
        grievance.status = new_status
        grievance.status_mr = STATUS_MR.get(new_status, new_status)
        grievance.resolved_date = date.today() if new_status == "Resolved" else None
        log_event(
            db, grievance, "status_changed", officer,
            from_status=previous, to_status=new_status,
            note=note,
        )

    if (new_priority := data.get("priority")) is not None and new_priority != grievance.priority:
        previous_priority = grievance.priority
        grievance.priority = new_priority
        grievance.priority_mr = PRIORITY_MR.get(new_priority, new_priority)
        grievance.auto_classified = False
        log_event(
            db, grievance, "priority_changed", officer,
            note=f"Priority changed from {previous_priority} to {new_priority}",
            note_mr=f"प्राधान्य {previous_priority} वरून {new_priority} करण्यात आले",
        )

    if (new_category := data.get("category")) is not None:
        grievance.category = new_category
        grievance.auto_classified = False

    if "officer_notes" in data:
        # A note without a status change is still worth showing the citizen.
        if note and data.get("status") is None:
            log_event(db, grievance, "note_added", officer, note=note)
        grievance.officer_notes = note

    if "department" in data and data["department"]:
        grievance.department = data["department"]

    db.commit()
    db.refresh(grievance)
    return grievance


@router.post("/classify", response_model=dict)
def preview_classification(
    body: GrievanceCreate, _: User = Depends(get_current_user)
) -> dict:
    """Run the classifier without saving — lets the submission form show the
    suggested category and priority before the citizen presses send."""
    result = classify(body.title, body.description)
    return {
        "category": result.category,
        "categoryMr": result.category_mr,
        "priority": result.priority,
        "priorityMr": result.priority_mr,
        "department": result.department,
        "departmentMr": result.department_mr,
        "matchedTerms": result.matched_terms,
    }
