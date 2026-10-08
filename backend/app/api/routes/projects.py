"""Development works: proposals, decisions, money and progress.

A work is opened as a proposal — usually out of one or more complaints — and
moves through the stages in `services/works.py`. Every route here that changes
one checks the work's village first, then lets that module decide whether the
step is allowed; this file's job is who may ask, not what the rules are.
"""

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api import presenters
from app.core.deps import (
    assert_can_access_village,
    get_current_user,
    require_officer,
    village_scope,
)
from app.db.session import get_db
from app.models import BudgetEntry, Facility, Grievance, Project, User, Village
from app.schemas import (
    BudgetEntryCreate,
    EntryCorrection,
    LinkGrievances,
    ProgressUpdate,
    ProjectCreate,
    ProjectDetail,
    ProjectOut,
    ProjectUpdate,
    ProposalCreate,
    StageDecision,
)
from app.services import timeline, works
from app.services.works import STATUS_MR, WorksError

router = APIRouter(prefix="/projects", tags=["projects"])


def _load(db: Session, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No project with that ID.")
    return project


def _owned(db: Session, project_id: str, user: User) -> Project:
    """Load a work and refuse it to anyone outside its village.

    The role alone used to be enough to change or delete any work in the block.
    """
    project = _load(db, project_id)
    assert_can_access_village(user, project.village_id)
    return project


def _refuse(exc: WorksError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


@router.get("", response_model=list[ProjectOut])
def list_projects(
    status_filter: str | None = None,
    stage: str | None = None,
    ward: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ProjectOut]:
    stmt = select(Project).options(
        selectinload(Project.entries), selectinload(Project.grievances)
    )
    scope = village_scope(user)
    if scope is not None:
        stmt = stmt.where(Project.village_id == scope)
    if status_filter:
        stmt = stmt.where(Project.status == status_filter)
    if stage:
        stmt = stmt.where(Project.stage == stage)
    if ward is not None:
        stmt = stmt.where(Project.ward == ward)
    rows = db.scalars(stmt.order_by(Project.ward, Project.name))
    return [presenters.project_out(p) for p in rows]


@router.get("/vocabulary", response_model=dict)
def vocabulary(_: User = Depends(get_current_user)) -> dict:
    """The stages, funding sources, entry kinds and asset types, with labels.

    Served rather than copied into the frontend, so a stage renamed or a funding
    source added here appears on the screen without a second edit somewhere
    else. Declared above `/{project_id}` so "vocabulary" is not read as an ID.
    """
    def labelled(table: dict[str, tuple[str, str]]) -> list[dict]:
        return [{"code": c, "label": en, "labelMr": mr} for c, (en, mr) in table.items()]

    def stage(code: str) -> dict:
        label, label_mr = works.STAGE_LABELS[code]
        return {"code": code, "label": label, "labelMr": label_mr}

    return {
        # The eight that happen in order, and the two that sit to the side.
        "stages": [stage(code) for code in works.STAGES],
        "sideStages": [stage(code) for code in ("rejected", "on_hold")],
        "fundingSources": labelled(works.FUNDING_SOURCES),
        "entryKinds": labelled(works.KIND_LABELS),
        "assetTypes": labelled(works.ASSET_TYPES),
    }


@router.get("/{project_id}", response_model=ProjectDetail)
def get_project(
    project_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectDetail:
    project = _owned(db, project_id, user)
    return presenters.project_detail(project, user)


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
    body: ProjectCreate,
    officer: User = Depends(require_officer),
    db: Session = Depends(get_db),
) -> ProjectOut:
    """Register a work that is already under way, from its sanctioned and spent
    totals. A new work should be opened as a proposal instead — see
    `POST /projects/proposals` — so that its approval and its money are on the
    record from the start rather than summarised afterwards.
    """
    project_id = body.id or f"proj_{uuid4().hex[:10]}"
    if db.get(Project, project_id):
        raise HTTPException(status.HTTP_409_CONFLICT, "That project ID is already in use.")
    if body.utilized > body.budget:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Utilised amount cannot exceed the sanctioned budget.",
        )
    data = body.model_dump(exclude={"id"})
    for field in ("name", "description", "location"):
        data[f"{field}_mr"] = data[f"{field}_mr"] or data[field]
    data["status_mr"] = STATUS_MR[body.status]
    project = Project(id=project_id, village_id=village_scope(officer), **data)
    db.add(project)
    db.flush()
    # The two totals become opening entries, so this work's money is held the
    # same way as every other's from here on.
    works.open_ledger(db, project, actor=officer)
    timeline.project_event(
        db, project, "registered", officer, to_stage=project.stage,
        note="Registered as a work already under way.",
        note_mr="आधीपासून सुरू असलेले काम म्हणून नोंद.",
    )
    db.commit()
    db.refresh(project)
    return presenters.project_out(project)


@router.post(
    "/proposals", response_model=ProjectDetail, status_code=status.HTTP_201_CREATED
)
def create_proposal(
    body: ProposalCreate,
    officer: User = Depends(require_officer),
    db: Session = Depends(get_db),
) -> ProjectDetail:
    """Open a proposed work, usually from one or more complaints.

    This is the step that turns "we need twenty streetlights" from a complaint
    nobody can close into a work somebody can decide on. The complaints are
    linked, not merged: each resident keeps their own, pointing at this.
    """
    grievances: list[Grievance] = []
    for grievance_id in dict.fromkeys(body.grievance_ids):
        grievance = db.get(Grievance, grievance_id)
        if grievance is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"No grievance with ID {grievance_id}.")
        assert_can_access_village(officer, grievance.village_id)
        grievances.append(grievance)

    village_id = village_scope(officer) or body.village_id or (
        grievances[0].village_id if grievances else None
    )
    if village_id is None or db.get(Village, village_id) is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Say which Gram Panchayat this work is for."
        )

    if body.asset_type and body.asset_type not in works.ASSET_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "That is not a recognised asset type.")

    # Where the work is: what the officer gave, else where the first complaint
    # was reported, else the village centre. An officer turning a complaint
    # into a proposal should not have to look up coordinates to do it.
    latitude, longitude = body.latitude, body.longitude
    if latitude is None or longitude is None:
        located = next(
            (g for g in grievances if g.latitude is not None and g.longitude is not None), None
        )
        if located is not None:
            latitude, longitude = located.latitude, located.longitude
        else:
            village = db.get(Village, village_id)
            latitude, longitude = village.latitude, village.longitude
    if latitude is None or longitude is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "This village has no centre point on record. Give the location of the work.",
        )

    unit_label, unit_label_mr = body.unit_label, body.unit_label_mr
    if body.units_planned and not unit_label:
        unit_label, unit_label_mr = "units", unit_label_mr or "घटक"
    try:
        project = works.propose(
            db, officer,
            village_id=village_id,
            name=body.name.strip(),
            name_mr=(body.name_mr or body.name).strip(),
            description=body.description.strip(),
            description_mr=(body.description_mr or body.description).strip(),
            ward=body.ward,
            location=body.location.strip(),
            location_mr=(body.location_mr or body.location).strip(),
            latitude=latitude,
            longitude=longitude,
            category=body.category or (grievances[0].category if grievances else None),
            units_planned=body.units_planned,
            unit_label=unit_label,
            unit_label_mr=unit_label_mr or unit_label,
            asset_type=body.asset_type,
            expected_completion=body.expected_completion,
        )
        works.link_grievances(db, project, grievances, officer)
        if body.estimate is not None:
            # The officer's own first figure for what it will cost, entered with
            # the proposal rather than as a second step. It is an estimate entry
            # like any other: dated, attributed, and revisable.
            works.add_entry(
                db, project, officer,
                kind="estimate", amount=body.estimate, note=body.estimate_note,
            )
    except WorksError as exc:
        db.rollback()
        raise _refuse(exc) from exc

    db.commit()
    db.refresh(project)
    return presenters.project_detail(project, officer)


@router.post("/{project_id}/decisions", response_model=ProjectDetail)
def decide(
    project_id: str,
    body: StageDecision,
    officer: User = Depends(require_officer),
    db: Session = Depends(get_db),
) -> ProjectDetail:
    """Verify, approve, reject, start, complete, hold or resume a work."""
    project = _owned(db, project_id, officer)
    try:
        works.act(
            db, project, body.action, officer,
            note=body.note, sabha_meeting_id=body.sabha_meeting_id,
        )
    except WorksError as exc:
        db.rollback()
        raise _refuse(exc) from exc
    db.commit()
    db.refresh(project)
    return presenters.project_detail(project, officer)


@router.post(
    "/{project_id}/budget-entries",
    response_model=ProjectDetail,
    status_code=status.HTTP_201_CREATED,
)
def add_budget_entry(
    project_id: str,
    body: BudgetEntryCreate,
    officer: User = Depends(require_officer),
    db: Session = Depends(get_db),
) -> ProjectDetail:
    """Record one step in a work's money: an estimate, a request, an approval,
    funds arriving, or a payment. Entries are never edited — a revision is a
    new entry, and the earlier figure stays on the record."""
    project = _owned(db, project_id, officer)
    try:
        works.add_entry(
            db, project, officer,
            kind=body.kind, amount=body.amount, entry_date=body.entry_date,
            funding_source=body.funding_source, reference=body.reference, note=body.note,
        )
    except WorksError as exc:
        db.rollback()
        raise _refuse(exc) from exc
    db.commit()
    db.refresh(project)
    return presenters.project_detail(project, officer)


@router.post(
    "/{project_id}/budget-entries/{entry_id}/corrections",
    response_model=ProjectDetail,
    status_code=status.HTTP_201_CREATED,
)
def correct_budget_entry(
    project_id: str,
    entry_id: str,
    body: EntryCorrection,
    officer: User = Depends(require_officer),
    db: Session = Depends(get_db),
) -> ProjectDetail:
    """Put right a receipt or a payment that was recorded wrongly.

    The entry is not edited. A correcting line is added that carries the
    difference and the reason, so the ledger still shows what was first
    recorded, what it was changed to, by whom and why.
    """
    project = _owned(db, project_id, officer)
    entry = db.get(BudgetEntry, entry_id)
    if entry is None or entry.project_id != project.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such entry on this work.")
    try:
        works.correct_entry(
            db, project, officer, entry, amount=body.amount, reason=body.reason,
        )
    except WorksError as exc:
        db.rollback()
        raise _refuse(exc) from exc
    db.commit()
    db.refresh(project)
    return presenters.project_detail(project, officer)


@router.post("/{project_id}/progress", response_model=ProjectDetail)
def record_progress(
    project_id: str,
    body: ProgressUpdate,
    officer: User = Depends(require_officer),
    db: Session = Depends(get_db),
) -> ProjectDetail:
    project = _owned(db, project_id, officer)
    try:
        works.record_progress(
            db, project, officer,
            units_done=body.units_done, progress=body.progress, note=body.note,
        )
    except WorksError as exc:
        db.rollback()
        raise _refuse(exc) from exc
    db.commit()
    db.refresh(project)
    return presenters.project_detail(project, officer)


@router.post("/{project_id}/grievances", response_model=ProjectDetail)
def link_grievances(
    project_id: str,
    body: LinkGrievances,
    officer: User = Depends(require_officer),
    db: Session = Depends(get_db),
) -> ProjectDetail:
    """Attach more complaints to a work — the residents who reported the same
    problem after the proposal was opened."""
    project = _owned(db, project_id, officer)
    grievances = []
    for grievance_id in dict.fromkeys(body.grievance_ids):
        grievance = db.get(Grievance, grievance_id)
        if grievance is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"No grievance with ID {grievance_id}.")
        assert_can_access_village(officer, grievance.village_id)
        grievances.append(grievance)
    try:
        works.link_grievances(db, project, grievances, officer)
    except WorksError as exc:
        db.rollback()
        raise _refuse(exc) from exc
    db.commit()
    db.refresh(project)
    return presenters.project_detail(project, officer)


@router.delete("/{project_id}/grievances/{grievance_id}", response_model=ProjectDetail)
def unlink_grievance(
    project_id: str,
    grievance_id: str,
    officer: User = Depends(require_officer),
    db: Session = Depends(get_db),
) -> ProjectDetail:
    project = _owned(db, project_id, officer)
    grievance = db.get(Grievance, grievance_id)
    if grievance is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No grievance with that ID.")
    try:
        works.unlink_grievance(db, project, grievance, officer)
    except WorksError as exc:
        db.rollback()
        raise _refuse(exc) from exc
    db.commit()
    db.refresh(project)
    return presenters.project_detail(project, officer)


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: str,
    body: ProjectUpdate,
    officer: User = Depends(require_officer),
    db: Session = Depends(get_db),
) -> ProjectOut:
    project = _owned(db, project_id, officer)
    data = body.model_dump(exclude_unset=True)

    if data.get("utilized") is not None:
        # One way to record money. A total typed into a form has no date, no
        # reference and no history, and would quietly disagree with the ledger.
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Spending is recorded as dated entries now, not as a total. Use "
            "“Record spending” on the work (POST /projects/{id}/budget-entries, "
            "kind “spent”).",
        )

    try:
        if (planned := data.get("units_planned")) is not None:
            if project.stage in ("completed", "rejected"):
                raise WorksError("The planned number cannot be changed on a closed work.", 409)
            if planned < (project.units_done or 0):
                raise WorksError(
                    f"{project.units_done} are already recorded as done, so the plan "
                    f"cannot be reduced below that."
                )
            previous = project.units_planned
            project.units_planned = planned
            project.unit_label = project.unit_label or "units"
            project.progress = works.physical_percent(project)
            timeline.project_event(
                db, project, "updated", officer,
                note=f"Planned number revised from {previous or 'none'} to {planned}.",
                note_mr=f"नियोजित संख्या {previous or '—'} वरून {planned} केली.",
            )

        if (progress := data.get("progress")) is not None:
            if project.stage == "completed":
                if progress != 100:
                    raise WorksError("This work is already complete.", 409)
            elif progress == 100 and not project.units_planned:
                # Reaching 100% is the work being finished, so it goes through
                # the same door as pressing Complete.
                works.act(db, project, "complete", officer)
            else:
                works.record_progress(db, project, officer, progress=progress)

        if (new_status := data.get("status")) is not None:
            if new_status == "Completed":
                if project.stage != "completed":
                    works.act(db, project, "complete", officer)
            else:
                if project.stage != "in_progress":
                    raise WorksError(
                        "Only a work in progress can be marked delayed or on time.", 409
                    )
                if new_status != project.status:
                    project.status = new_status
                    project.status_mr = STATUS_MR[new_status]
                    timeline.project_event(
                        db, project, "updated", officer,
                        note=f"Marked {new_status.lower()}.",
                        note_mr=f"“{STATUS_MR[new_status]}” म्हणून नोंद.",
                    )
    except WorksError as exc:
        db.rollback()
        raise _refuse(exc) from exc

    if data.get("description"):
        project.description = data["description"]
    if "expected_completion" in data:
        project.expected_completion = data["expected_completion"]

    db.commit()
    db.refresh(project)
    return presenters.project_out(project)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: str,
    officer: User = Depends(require_officer),
    db: Session = Depends(get_db),
) -> None:
    project = _owned(db, project_id, officer)
    # Explicit rather than left to the foreign key: SQLite does not enforce
    # ON DELETE SET NULL unless asked to, and a complaint pointing at a work
    # that no longer exists would break its owner's tracking page.
    for grievance in list(project.grievances):
        grievance.project_id = None
    # The same for anything it built. Deleting the record of a work does not
    # take twenty streetlights off their poles, so the asset stays in the
    # register and loses only the note of which work put it there.
    for facility in db.scalars(select(Facility).where(Facility.project_id == project.id)):
        facility.project_id = None
    db.delete(project)
    db.commit()
