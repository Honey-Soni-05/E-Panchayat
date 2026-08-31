"""The administrative hierarchy: states, districts, blocks and villages.

Every unit carries its official Local Government Directory code, so a record in
this system can be matched against government data rather than only against
itself.

Note the convention used across this API: request and response *bodies* are
camelCase for the React client, while *query parameters* stay snake_case
(only_active, include_feed, facility_type).
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.deps import get_current_user, require_admin, village_scope
from app.db.session import get_db
from app.models import Block, Citizen, District, Grievance, Project, User, Village
from app.schemas import PublicVillage, VillageDetail, VillageOut, VillageSummary

router = APIRouter(tags=["villages"])


def _to_out(village: Village) -> VillageOut:
    block = village.block
    district = block.district if block else None
    state = district.state if district else None
    return VillageOut(
        id=village.id,
        name=village.name,
        name_mr=village.name_mr,
        lgd_code=village.lgd_code,
        census_code_2011=village.census_code_2011,
        block_id=village.block_id,
        block_name=block.name if block else "",
        block_name_mr=block.name_mr if block else "",
        district_name=district.name if district else "",
        district_name_mr=district.name_mr if district else "",
        state_name=state.name if state else "",
        state_name_mr=state.name_mr if state else "",
        latitude=village.latitude,
        longitude=village.longitude,
        population_2011=village.population_2011,
        households_2011=village.households_2011,
        ward_count=village.ward_count,
        gram_panchayat_status=village.gram_panchayat_status,
        notes=village.notes,
    )


def _load(db: Session):
    return select(Village).options(
        selectinload(Village.block)
        .selectinload(Block.district)
        .selectinload(District.state)
    )


@router.get("/villages", response_model=list[VillageOut])
def list_villages(
    block_id: str | None = None,
    only_active: bool = Query(
        False, description="Exclude villages absorbed into a municipal corporation"
    ),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[VillageOut]:
    stmt = _load(db)

    # An officer only ever sees their own Gram Panchayat in the picker.
    scope = village_scope(user)
    if scope is not None:
        stmt = stmt.where(Village.id == scope)
    if block_id:
        stmt = stmt.where(Village.block_id == block_id)
    if only_active:
        stmt = stmt.where(Village.gram_panchayat_status == "active")

    return [_to_out(v) for v in db.scalars(stmt.order_by(Village.name))]


@router.get("/villages/current", response_model=VillageOut | None)
def current_village(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> VillageOut | None:
    """The village this signed-in user works in.

    Null for an admin, who works across the district — the frontend uses that
    to decide whether to show a village picker in the header.
    """
    village_id = user.village_id
    if not village_id and user.citizen_id:
        citizen = db.get(Citizen, user.citizen_id)
        village_id = citizen.village_id if citizen else None
    if not village_id:
        return None

    village = db.scalar(_load(db).where(Village.id == village_id))
    return _to_out(village) if village else None


@router.get("/villages/public", response_model=list[PublicVillage])
def public_villages(db: Session = Depends(get_db)) -> list[PublicVillage]:
    """Village names for the sign-up form, without a token.

    Somebody applying for an account has no session yet, so they need this to
    say which Gram Panchayat they live in. Only the name and its LGD code are
    exposed — that is published government data, and nothing about residents,
    budgets or grievances is reachable here.

    Declared above /villages/{village_id} so "public" is not read as an id.
    """
    villages = db.scalars(
        select(Village)
        .where(Village.gram_panchayat_status == "active")
        .order_by(Village.name)
    )
    return [
        PublicVillage(id=v.id, name=v.name, name_mr=v.name_mr, lgd_code=v.lgd_code)
        for v in villages
    ]


@router.get("/villages/{village_id}", response_model=VillageDetail)
def get_village(
    village_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> VillageDetail:
    scope = village_scope(user)
    if scope is not None and scope != village_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "That village belongs to another Gram Panchayat."
        )

    village = db.scalar(_load(db).where(Village.id == village_id))
    if village is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No village with that ID.")

    def count(model, *where) -> int:
        return db.scalar(select(func.count()).select_from(model).where(*where)) or 0

    return VillageDetail(
        **_to_out(village).model_dump(by_alias=False),
        registered_citizens=count(Citizen, Citizen.village_id == village_id),
        open_grievances=count(
            Grievance, Grievance.village_id == village_id, Grievance.status != "Resolved"
        ),
        active_projects=count(
            Project, Project.village_id == village_id, Project.status != "Completed"
        ),
    )


@router.get("/districts/summary", response_model=list[VillageSummary])
def district_summary(
    _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> list[VillageSummary]:
    """Every village in the district with its headline numbers.

    Admin only. This is the district-level rollup the synopsis describes, and
    it exists because the hierarchy is modelled properly — it is one grouped
    query, not a separate system.
    """
    citizens = dict(
        db.execute(
            select(Citizen.village_id, func.count()).group_by(Citizen.village_id)
        ).all()
    )
    grievances = dict(
        db.execute(
            select(Grievance.village_id, func.count())
            .where(Grievance.status != "Resolved")
            .group_by(Grievance.village_id)
        ).all()
    )
    projects = dict(
        db.execute(
            select(Project.village_id, func.count())
            .where(Project.status != "Completed")
            .group_by(Project.village_id)
        ).all()
    )

    out: list[VillageSummary] = []
    for village in db.scalars(_load(db).order_by(Village.name)):
        out.append(
            VillageSummary(
                id=village.id,
                name=village.name,
                name_mr=village.name_mr,
                lgd_code=village.lgd_code,
                population_2011=village.population_2011,
                gram_panchayat_status=village.gram_panchayat_status,
                registered_citizens=citizens.get(village.id, 0),
                open_grievances=grievances.get(village.id, 0),
                active_projects=projects.get(village.id, 0),
            )
        )

    # Villages with data first — that is where an administrator's attention goes.
    out.sort(key=lambda v: (-v.registered_citizens, v.name))
    return out
