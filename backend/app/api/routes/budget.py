"""The Panchayat's budget across all its works.

Open to everyone in the village, residents included. What a Gram Panchayat has
sanctioned, received and spent on public works is public information, and there
is nothing about any individual in it — the table lists works, not people. An
officer and a resident of the same village see the same figures.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api import presenters
from app.core.deps import get_current_user, village_scope
from app.db.session import get_db
from app.models import User
from app.schemas import (
    BudgetOverview,
    BudgetProjectRow,
    BudgetSourceRow,
    BudgetTotals,
    ProjectSteps,
)
from app.services import budget, works
from app.services.works import WorksError

router = APIRouter(prefix="/budget", tags=["budget"])


@router.get("/overview", response_model=BudgetOverview)
def budget_overview(
    fy: str | None = None,
    village_id: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BudgetOverview:
    """Totals, a row per work, and a row per funding source.

    `fy` limits it to entries dated in one financial year ("2026-27"); leave it
    out for everything on record. `village_id` is read only for an admin, who
    otherwise gets the whole block.
    """
    scope = village_scope(user)
    if scope is None:
        scope = village_id

    try:
        data = budget.overview(db, scope, fy)
    except WorksError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    rows = []
    for item in data["rows"]:
        project, m = item["project"], item["money"]
        label, label_mr = works.stage_label(project.stage)
        source, source_mr = works.FUNDING_SOURCES.get(
            project.funding_source or "", (None, None)
        )
        rows.append(BudgetProjectRow(
            id=project.id, name=project.name, name_mr=project.name_mr, ward=project.ward,
            stage=project.stage, stage_label=label, stage_label_mr=label_mr,
            status=project.status,
            funding_source=project.funding_source,
            funding_source_label=source, funding_source_label_mr=source_mr,
            estimated=m.estimated, requested=m.requested, approved=m.approved,
            received=m.received, spent=m.spent, balance=m.balance,
            remaining=m.remaining,
            physical_percent=works.physical_percent(project),
            financial_percent=m.financial_percent,
            flags=presenters.flags_out(project, works.money(project.entries)),
            # From the whole ledger, not the year on screen: what can be
            # recorded next does not depend on which year is being looked at.
            steps=ProjectSteps(**works.next_steps(project)),
        ))

    return BudgetOverview(
        financial_year=data["financial_year"],
        financial_years=data["financial_years"],
        totals=BudgetTotals(**data["totals"]),
        projects=rows,
        sources=[BudgetSourceRow(**s) for s in data["sources"]],
        stage_counts=data["stage_counts"],
    )
