"""Citizens and families."""

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import assert_can_read_citizen, get_current_user, require_officer
from app.db.session import get_db
from app.models import Citizen, Family, User
from app.schemas import (
    CitizenCreate,
    CitizenOut,
    CitizenUpdate,
    FamilyMemberOut,
    FamilyOut,
)

router = APIRouter(tags=["citizens"])


def _to_out(c: Citizen) -> CitizenOut:
    """Rebuild the shape the React components expect, including the family
    members list that used to be denormalised onto every citizen row."""
    members = [
        FamilyMemberOut(
            id=m.id, name=m.name, name_mr=m.name_mr,
            relation=m.relation, relation_mr=m.relation_mr,
            age=m.age, is_head=m.is_head,
        )
        for m in (c.family.members if c.family else [])
        if m.id != c.id
    ]
    return CitizenOut(
        id=c.id, name=c.name, name_mr=c.name_mr, age=c.age,
        gender=c.gender, gender_mr=c.gender_mr,
        occupation=c.occupation, occupation_mr=c.occupation_mr,
        income=float(c.income or 0), ward=c.ward, phone=c.phone,
        family_id=c.family_id, relation=c.relation, relation_mr=c.relation_mr,
        is_head=c.is_head, date_of_birth=c.date_of_birth,
        family_name=c.family.name if c.family else None,
        family_name_mr=c.family.name_mr if c.family else None,
        family_members=members,
        created_at=c.created_at,
    )


@router.get("/citizens", response_model=list[CitizenOut])
def list_citizens(
    search: str | None = Query(None, description="Match name, id or phone"),
    ward: int | None = None,
    limit: int = Query(200, le=1000),
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CitizenOut]:
    # A citizen sees exactly one row: their own.
    if user.role == "citizen":
        if not user.citizen_id:
            return []
        c = db.get(Citizen, user.citizen_id)
        return [_to_out(c)] if c else []

    stmt = select(Citizen).options(
        selectinload(Citizen.family).selectinload(Family.members)
    )
    if ward is not None:
        stmt = stmt.where(Citizen.ward == ward)
    if search:
        pattern = f"%{search.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Citizen.name).like(pattern),
                func.lower(Citizen.name_mr).like(pattern),
                func.lower(Citizen.id).like(pattern),
                func.lower(Citizen.phone).like(pattern),
            )
        )
    stmt = stmt.order_by(Citizen.ward, Citizen.name).limit(limit).offset(offset)
    return [_to_out(c) for c in db.scalars(stmt)]


@router.get("/citizens/{citizen_id}", response_model=CitizenOut)
def get_citizen(
    citizen_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CitizenOut:
    assert_can_read_citizen(user, citizen_id)
    citizen = db.get(Citizen, citizen_id)
    if citizen is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No citizen with that ID.")
    return _to_out(citizen)


@router.post("/citizens", response_model=CitizenOut, status_code=status.HTTP_201_CREATED)
def create_citizen(
    body: CitizenCreate,
    _: User = Depends(require_officer),
    db: Session = Depends(get_db),
) -> CitizenOut:
    citizen_id = body.id or f"cit_{uuid4().hex[:10]}"
    if db.get(Citizen, citizen_id):
        raise HTTPException(status.HTTP_409_CONFLICT, "That citizen ID is already in use.")
    if body.family_id and not db.get(Family, body.family_id):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No family with that ID.")

    citizen = Citizen(id=citizen_id, **body.model_dump(exclude={"id"}))
    db.add(citizen)
    db.commit()
    db.refresh(citizen)
    return _to_out(citizen)


@router.patch("/citizens/{citizen_id}", response_model=CitizenOut)
def update_citizen(
    citizen_id: str,
    body: CitizenUpdate,
    _: User = Depends(require_officer),
    db: Session = Depends(get_db),
) -> CitizenOut:
    citizen = db.get(Citizen, citizen_id)
    if citizen is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No citizen with that ID.")

    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(citizen, field, value)
    db.commit()
    db.refresh(citizen)
    return _to_out(citizen)


@router.delete("/citizens/{citizen_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_citizen(
    citizen_id: str,
    _: User = Depends(require_officer),
    db: Session = Depends(get_db),
) -> None:
    citizen = db.get(Citizen, citizen_id)
    if citizen is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No citizen with that ID.")
    db.delete(citizen)
    db.commit()


@router.get("/families", response_model=list[FamilyOut])
def list_families(
    _: User = Depends(require_officer), db: Session = Depends(get_db)
) -> list[Family]:
    stmt = select(Family).options(selectinload(Family.members)).order_by(Family.name)
    return list(db.scalars(stmt))
