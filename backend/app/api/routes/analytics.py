"""Dashboard figures, chart series and map facilities.

Every number the dashboards show is computed here from the database, so the
officer view and the citizen view cannot disagree, and nothing depends on what
happens to be cached in one browser.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_officer, village_scope
from app.db.session import get_db
from app.models import (
    Citizen,
    CitizenDocument,
    Facility,
    Family,
    Grievance,
    Project,
    SabhaMeeting,
    User,
)
from app.schemas import DashboardStats, FacilityOut, NamedCount

router = APIRouter(tags=["analytics"])


@router.get("/facilities", response_model=list[FacilityOut])
def list_facilities(
    facility_type: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Facility]:
    stmt = select(Facility)
    scope = village_scope(user)
    if scope is not None:
        stmt = stmt.where(Facility.village_id == scope)
    if facility_type:
        stmt = stmt.where(Facility.facility_type == facility_type)
    return list(db.scalars(stmt.order_by(Facility.name)))


@router.get("/analytics/dashboard", response_model=DashboardStats)
def dashboard(
    user: User = Depends(require_officer), db: Session = Depends(get_db)
) -> DashboardStats:
    # Every figure below is scoped to the officer's own Gram Panchayat, so two
    # officers in different villages never see each other's numbers.
    scope = village_scope(user)

    def scoped(model, *where):
        clauses = list(where)
        if scope is not None and hasattr(model, "village_id"):
            clauses.append(model.village_id == scope)
        return clauses

    def count(model, *where) -> int:
        return db.scalar(
            select(func.count()).select_from(model).where(*scoped(model, *where))
        ) or 0

    # A proposal the Panchayat turned down may have had a budget approved before
    # it was. That money is not committed to anything, so it is left out here,
    # as it is on the budget screen.
    budget_stmt = select(func.coalesce(func.sum(Project.budget), 0)).where(
        Project.stage != "rejected"
    )
    used_stmt = select(func.coalesce(func.sum(Project.utilized), 0)).where(
        Project.stage != "rejected"
    )
    if scope is not None:
        budget_stmt = budget_stmt.where(Project.village_id == scope)
        used_stmt = used_stmt.where(Project.village_id == scope)
    total_budget = db.scalar(budget_stmt) or 0
    total_utilized = db.scalar(used_stmt) or 0

    # Two figures the helper above could not scope. `scoped()` adds the village
    # filter only when the model has a `village_id` column, and quietly adds
    # nothing when it does not — so a document, which belongs to a village only
    # through its resident, was counted across the whole block. Written out
    # explicitly here so the join is visible.
    meeting_stmt = select(func.max(SabhaMeeting.meeting_date))
    pending_docs_stmt = (
        select(func.count())
        .select_from(CitizenDocument)
        .where(CitizenDocument.status == "Pending Verification")
    )
    if scope is not None:
        meeting_stmt = meeting_stmt.where(SabhaMeeting.village_id == scope)
        pending_docs_stmt = pending_docs_stmt.join(
            Citizen, CitizenDocument.citizen_id == Citizen.id
        ).where(Citizen.village_id == scope)
    next_meeting = db.scalar(meeting_stmt)
    pending_documents = db.scalar(pending_docs_stmt) or 0

    return DashboardStats(
        total_citizens=count(Citizen),
        total_families=count(Family),
        open_grievances=count(Grievance, Grievance.status != "Resolved"),
        critical_grievances=count(
            Grievance, Grievance.priority == "Critical", Grievance.status != "Resolved"
        ),
        resolved_grievances=count(Grievance, Grievance.status == "Resolved"),
        # A work is active once it has started. A proposal still waiting on a
        # decision or on money is planned, and counting it here would show a
        # Panchayat as building things it has only been asked for.
        active_projects=count(Project, Project.status.in_(("Ongoing", "Delayed"))),
        delayed_projects=count(Project, Project.status == "Delayed"),
        planned_projects=count(Project, Project.status == "Planned"),
        budget_pending_projects=count(Project, Project.stage == "budget_requested"),
        total_budget=float(total_budget),
        total_utilized=float(total_utilized),
        pending_documents=pending_documents,
        next_meeting_date=next_meeting,
    )


# The four breakdowns below sit beside the dashboard totals on the same screen.
# The totals were scoped to the officer's village and these were not, so an
# officer shown "0 residents" was shown their neighbour's complaints by ward and
# budgets by project in the charts underneath. Each takes the same scope now.

def _in_village(model, user: User) -> list:
    scope = village_scope(user)
    return [model.village_id == scope] if scope is not None else []


@router.get("/analytics/age-distribution", response_model=list[NamedCount])
def age_distribution(
    user: User = Depends(require_officer), db: Session = Depends(get_db)
) -> list[NamedCount]:
    buckets = [
        ("0-17", "०-१७", 0, 17),
        ("18-35", "१८-३५", 18, 35),
        ("36-59", "३६-५९", 36, 59),
        ("60+", "६०+", 60, 200),
    ]
    out = []
    for label, label_mr, low, high in buckets:
        n = db.scalar(
            select(func.count())
            .select_from(Citizen)
            .where(Citizen.age >= low, Citizen.age <= high, *_in_village(Citizen, user))
        )
        out.append(NamedCount(label=label, label_mr=label_mr, value=n or 0))
    return out


@router.get("/analytics/grievances-by-department", response_model=list[NamedCount])
def grievances_by_department(
    user: User = Depends(require_officer), db: Session = Depends(get_db)
) -> list[NamedCount]:
    rows = db.execute(
        select(Grievance.department, Grievance.department_mr, func.count())
        .where(*_in_village(Grievance, user))
        .group_by(Grievance.department, Grievance.department_mr)
        .order_by(func.count().desc())
    ).all()
    return [NamedCount(label=d, label_mr=d_mr, value=n) for d, d_mr, n in rows]


@router.get("/analytics/grievances-by-ward", response_model=list[NamedCount])
def grievances_by_ward(
    user: User = Depends(require_officer), db: Session = Depends(get_db)
) -> list[NamedCount]:
    rows = db.execute(
        select(Grievance.ward, func.count())
        .where(Grievance.status != "Resolved", *_in_village(Grievance, user))
        .group_by(Grievance.ward)
        .order_by(Grievance.ward)
    ).all()
    return [NamedCount(label=f"Ward {w}", label_mr=f"वॉर्ड {w}", value=n) for w, n in rows]


@router.get("/analytics/project-budgets", response_model=list[dict])
def project_budgets(
    user: User = Depends(require_officer), db: Session = Depends(get_db)
) -> list[dict]:
    """Budget vs. expenditure per project, in lakhs — the units the charts use."""
    # Only works with money sanctioned. A proposal that has not reached a budget
    # decision would otherwise sit in the chart as an empty pair of bars.
    projects = db.scalars(
        select(Project)
        .where(Project.budget > 0, *_in_village(Project, user))
        .order_by(Project.ward, Project.name)
    )
    return [
        {
            "id": p.id,
            "name": p.name,
            "nameMr": p.name_mr,
            "ward": p.ward,
            "status": p.status,
            "progress": p.progress,
            "budgetLakh": round(float(p.budget) / 100_000, 2),
            "utilizedLakh": round(float(p.utilized) / 100_000, 2),
        }
        for p in projects
    ]
