"""The Panchayat's money across all its works: a roll-up of the ledgers.

Nothing here is stored. Every figure is the sum of entries officers recorded
against individual works, added up on request, so the overview cannot disagree
with the works it summarises — there is no second set of numbers to keep in
step.

That is also its limit, and the reason this is called budget tracking and not
accounts. It answers "how much has been sanctioned, how much has arrived, how
much has been paid, and against which works". It does not answer what an
accountant would ask next: there are no vouchers behind the payments, no
opening and closing balances carried between years, and nothing is reconciled
against a bank statement or PFMS.

**Financial years.** With a year selected, only entries *dated* in it are
counted, so a work sanctioned in one year and built in the next shows its
approval in the first and its spending in the second. A work with nothing dated
in the selected year is left out of that year's table.
"""

from __future__ import annotations

from collections import Counter
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core import clock
from app.models import Project
from app.services import works


def _in_window(day: date, within: tuple[date, date] | None) -> bool:
    return within is None or within[0] <= day <= within[1]


def overview(db: Session, village_id: str | None, fy: str | None = None) -> dict:
    stmt = select(Project).options(
        selectinload(Project.entries), selectinload(Project.grievances)
    )
    if village_id is not None:
        stmt = stmt.where(Project.village_id == village_id)
    projects = list(db.scalars(stmt.order_by(Project.ward, Project.name)))

    within = works.fy_bounds(fy) if fy else None

    years = {works.financial_year(clock.today())}
    for project in projects:
        years.update(works.financial_year(e.entry_date) for e in project.entries)

    totals = dict(
        estimated=0.0, requested_pending=0.0, approved=0.0,
        received=0.0, spent=0.0, awaiting=0.0, balance=0.0, remaining=0.0,
    )
    rows: list[dict] = []
    by_source: dict[str | None, dict] = {}
    stage_counts: Counter[str] = Counter()

    def source_row(code: str | None) -> dict:
        return by_source.setdefault(
            code, dict(approved=0.0, received=0.0, spent=0.0, projects=set())
        )

    for project in projects:
        stage_counts[project.stage] += 1
        dated = [e for e in project.entries if _in_window(e.entry_date, within)]
        if within is not None and not dated:
            continue

        m = works.money(project.entries, within)
        rows.append(dict(project=project, money=m))

        # A proposal the Panchayat turned down has no claim on the budget. It
        # stays in the table, so its estimate is not lost, and out of the totals.
        if project.stage == "rejected":
            continue

        totals["estimated"] += m.estimated or 0.0
        if project.stage == "budget_requested":
            totals["requested_pending"] += m.requested or 0.0
        totals["approved"] += m.approved or 0.0
        totals["received"] += m.received
        totals["spent"] += m.spent
        totals["awaiting"] += m.awaiting
        totals["balance"] += m.balance
        totals["remaining"] += m.remaining

        # By source. Receipts and payments carry their own source. An approval
        # is one current figure, so it goes to the source named on the entry
        # that currently stands — the latest one.
        latest_approval = None
        for entry in works.in_order(dated):
            if entry.kind == "received":
                row = source_row(entry.funding_source)
                row["received"] += float(entry.amount)
                row["projects"].add(project.id)
            elif entry.kind == "spent":
                row = source_row(entry.funding_source)
                row["spent"] += float(entry.amount)
                row["projects"].add(project.id)
            elif entry.kind == "approved":
                latest_approval = entry
        if latest_approval is not None:
            row = source_row(latest_approval.funding_source)
            row["approved"] += float(latest_approval.amount)
            row["projects"].add(project.id)

    approved = totals["approved"]
    totals["utilisation_percent"] = round(totals["spent"] / approved * 100) if approved else 0

    sources = []
    for code, row in by_source.items():
        label, label_mr = works.FUNDING_SOURCES.get(
            code or "", ("Source not recorded", "स्रोत नोंदवलेला नाही")
        )
        sources.append(dict(
            code=code, label=label, label_mr=label_mr,
            approved=row["approved"], received=row["received"], spent=row["spent"],
            projects=len(row["projects"]),
        ))
    sources.sort(key=lambda s: s["approved"], reverse=True)

    return dict(
        financial_year=fy,
        financial_years=sorted(years, reverse=True),
        totals=totals,
        rows=rows,
        sources=sources,
        stage_counts=dict(stage_counts),
    )
