"""Dashboard figures, chart series and map facilities.

Every number the dashboards show is computed here from the database, so the
officer view and the citizen view cannot disagree, and nothing depends on what
happens to be cached in one browser.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_officer
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
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Facility]:
    stmt = select(Facility)
    if facility_type:
        stmt = stmt.where(Facility.facility_type == facility_type)
    return list(db.scalars(stmt.order_by(Facility.name)))


@router.get("/analytics/dashboard", response_model=DashboardStats)
def dashboard(
    _: User = Depends(require_officer), db: Session = Depends(get_db)
) -> DashboardStats:
    def count(model, *where) -> int:
        return db.scalar(select(func.count()).select_from(model).where(*where)) or 0

    total_budget = db.scalar(select(func.coalesce(func.sum(Project.budget), 0))) or 0
    total_utilized = db.scalar(select(func.coalesce(func.sum(Project.utilized), 0))) or 0
    next_meeting = db.scalar(
        select(func.max(SabhaMeeting.meeting_date))
    )

    return DashboardStats(
        total_citizens=count(Citizen),
        total_families=count(Family),
        open_grievances=count(Grievance, Grievance.status != "Resolved"),
        critical_grievances=count(
            Grievance, Grievance.priority == "Critical", Grievance.status != "Resolved"
        ),
        resolved_grievances=count(Grievance, Grievance.status == "Resolved"),
        active_projects=count(Project, Project.status != "Completed"),
        delayed_projects=count(Project, Project.status == "Delayed"),
        total_budget=float(total_budget),
        total_utilized=float(total_utilized),
        pending_documents=count(
            CitizenDocument, CitizenDocument.status == "Pending Verification"
        ),
        next_meeting_date=next_meeting,
    )


@router.get("/analytics/age-distribution", response_model=list[NamedCount])
def age_distribution(
    _: User = Depends(require_officer), db: Session = Depends(get_db)
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
            .where(Citizen.age >= low, Citizen.age <= high)
        )
        out.append(NamedCount(label=label, label_mr=label_mr, value=n or 0))
    return out


@router.get("/analytics/grievances-by-department", response_model=list[NamedCount])
def grievances_by_department(
    _: User = Depends(require_officer), db: Session = Depends(get_db)
) -> list[NamedCount]:
    rows = db.execute(
        select(Grievance.department, Grievance.department_mr, func.count())
        .group_by(Grievance.department, Grievance.department_mr)
        .order_by(func.count().desc())
    ).all()
    return [NamedCount(label=d, label_mr=d_mr, value=n) for d, d_mr, n in rows]


@router.get("/analytics/grievances-by-ward", response_model=list[NamedCount])
def grievances_by_ward(
    _: User = Depends(require_officer), db: Session = Depends(get_db)
) -> list[NamedCount]:
    rows = db.execute(
        select(Grievance.ward, func.count())
        .where(Grievance.status != "Resolved")
        .group_by(Grievance.ward)
        .order_by(Grievance.ward)
    ).all()
    return [NamedCount(label=f"Ward {w}", label_mr=f"वॉर्ड {w}", value=n) for w, n in rows]


@router.get("/analytics/project-budgets", response_model=list[dict])
def project_budgets(
    _: User = Depends(require_officer), db: Session = Depends(get_db)
) -> list[dict]:
    """Budget vs. expenditure per project, in lakhs — the units the charts use."""
    projects = db.scalars(select(Project).order_by(Project.ward, Project.name))
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
