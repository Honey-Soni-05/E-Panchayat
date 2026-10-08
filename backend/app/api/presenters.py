"""Turn a complaint or a work into what the API sends.

A work's response is mostly derived: its stage label, where its money stands,
what looks wrong, what may be done next. None of that is stored, so none of it
can be returned by handing FastAPI the database row. It is assembled here, in
one place, because three routers need it — projects, the complaint that points
at a project, and the budget roll-up — and three copies of "how is approved
calculated" would be two too many.
"""

from __future__ import annotations

from app.models import BudgetEntry, Grievance, Project, User
from app.schemas import (
    BudgetEntryOut,
    GrievanceDetail,
    GrievanceEventOut,
    GrievanceOut,
    LinkedGrievance,
    ProjectBrief,
    ProjectDetail,
    ProjectEventOut,
    ProjectFinance,
    ProjectFlag,
    ProjectOut,
    ProjectSteps,
)
from app.services import works
from app.services.classifier import REQUEST_TYPE_MR


def _source_labels(code: str | None) -> tuple[str | None, str | None]:
    if not code:
        return None, None
    return works.FUNDING_SOURCES.get(code, (code, code))


def _stage_index(stage: str) -> int | None:
    """1-based position in the sequence; None for rejected or on hold."""
    return works.STAGES.index(stage) + 1 if stage in works.STAGES else None


def _residents(project: Project) -> int:
    """People, not complaints: one resident filing twice asked once."""
    return len({g.citizen_id or g.id for g in project.grievances})


def entry_out(entry: BudgetEntry, project: Project) -> BudgetEntryOut:
    label, label_mr = works.KIND_LABELS.get(entry.kind, (entry.kind, entry.kind))
    source, source_mr = _source_labels(entry.funding_source)
    corrected = any(e.corrects_id == entry.id for e in project.entries)
    return BudgetEntryOut(
        corrects_id=entry.corrects_id,
        corrected_to=works.recorded_amount(entry, project.entries) if corrected else None,
        can_correct=works.can_correct(project, entry),
        id=entry.id,
        kind=entry.kind,
        kind_label=label,
        kind_label_mr=label_mr,
        amount=float(entry.amount),
        entry_date=entry.entry_date,
        funding_source=entry.funding_source,
        funding_source_label=source,
        funding_source_label_mr=source_mr,
        reference=entry.reference,
        note=entry.note,
        created_by_name=entry.created_by_name,
        created_at=entry.created_at,
    )


def finance_out(m: works.Money) -> ProjectFinance:
    return ProjectFinance(
        estimated=m.estimated,
        requested=m.requested,
        approved=m.approved,
        received=m.received,
        spent=m.spent,
        awaiting=m.awaiting,
        balance=m.balance,
        remaining=m.remaining,
        financial_percent=m.financial_percent,
    )


def flags_out(project: Project, m: works.Money) -> list[ProjectFlag]:
    return [
        ProjectFlag(code=f.code, severity=f.severity, message=f.message, message_mr=f.message_mr)
        for f in works.flags(project, m)
    ]


def _project_fields(project: Project) -> dict:
    m = works.money(project.entries)
    label, label_mr = works.stage_label(project.stage)
    source, source_mr = _source_labels(project.funding_source)
    created = project.created_at.date() if project.created_at else None
    return dict(
        id=project.id,
        village_id=project.village_id,
        name=project.name,
        name_mr=project.name_mr,
        description=project.description,
        description_mr=project.description_mr,
        progress=works.physical_percent(project),
        budget=float(project.budget or 0),
        utilized=float(project.utilized or 0),
        status=project.status,
        status_mr=project.status_mr,
        ward=project.ward,
        location=project.location,
        location_mr=project.location_mr,
        latitude=project.latitude,
        longitude=project.longitude,
        start_date=project.start_date,
        expected_completion=project.expected_completion,
        stage=project.stage,
        stage_label=label,
        stage_label_mr=label_mr,
        stage_index=_stage_index(project.stage),
        stage_total=len(works.STAGES),
        stage_changed_at=project.stage_changed_at,
        days_in_stage=works.days_in_stage(project),
        held_from_stage=project.held_from_stage,
        category=project.category,
        units_planned=project.units_planned,
        units_done=project.units_done or 0,
        unit_label=project.unit_label,
        unit_label_mr=project.unit_label_mr,
        asset_type=project.asset_type,
        physical_percent=works.physical_percent(project),
        funding_source=project.funding_source,
        funding_source_label=source,
        funding_source_label_mr=source_mr,
        decision_note=project.decision_note,
        sabha_meeting_id=project.sabha_meeting_id,
        financial_year=works.financial_year(project.start_date or created) if (
            project.start_date or created
        ) else None,
        finance=finance_out(m),
        flags=flags_out(project, m),
        linked_grievances=len(project.grievances),
        residents_affected=_residents(project),
        steps=ProjectSteps(**works.next_steps(project, m)),
    )


def project_out(project: Project) -> ProjectOut:
    return ProjectOut(**_project_fields(project))


def project_detail(project: Project, viewer: User) -> ProjectDetail:
    """The full record. Who asked for the work is shown to officers only: a
    resident opening a public work sees how many people asked, not their names."""
    linked: list[LinkedGrievance] = []
    if viewer.role != "citizen":
        linked = [
            LinkedGrievance(
                id=g.id, title=g.title, title_mr=g.title_mr, ward=g.ward,
                status=g.status, priority=g.priority, citizen_name=g.citizen_name,
                submitted_date=g.submitted_date,
                citizen_feedback=g.citizen_feedback, feedback_note=g.feedback_note,
            )
            for g in sorted(project.grievances, key=lambda g: g.submitted_date)
        ]
    return ProjectDetail(
        **_project_fields(project),
        entries=[entry_out(e, project) for e in project.entries],
        events=[ProjectEventOut.model_validate(e) for e in project.events],
        grievances=linked,
    )


def project_brief(project: Project) -> ProjectBrief:
    m = works.money(project.entries)
    label, label_mr = works.stage_label(project.stage)
    return ProjectBrief(
        id=project.id,
        name=project.name,
        name_mr=project.name_mr,
        stage=project.stage,
        stage_label=label,
        stage_label_mr=label_mr,
        stage_index=_stage_index(project.stage),
        stage_total=len(works.STAGES),
        status=project.status,
        status_mr=project.status_mr,
        decision_note=project.decision_note,
        estimated=m.estimated,
        requested=m.requested,
        approved=m.approved,
        received=m.received,
        spent=m.spent,
        units_planned=project.units_planned,
        units_done=project.units_done or 0,
        unit_label=project.unit_label,
        unit_label_mr=project.unit_label_mr,
        physical_percent=works.physical_percent(project),
        expected_completion=project.expected_completion,
        linked_grievances=_residents(project),
        history=[ProjectEventOut.model_validate(e) for e in project.events],
    )


def _grievance_fields(grievance: Grievance, similar_count: int) -> dict:
    return dict(
        id=grievance.id,
        title=grievance.title,
        title_mr=grievance.title_mr,
        description=grievance.description,
        description_mr=grievance.description_mr,
        category=grievance.category,
        category_mr=grievance.category_mr,
        priority=grievance.priority,
        priority_mr=grievance.priority_mr,
        status=grievance.status,
        status_mr=grievance.status_mr,
        department=grievance.department,
        department_mr=grievance.department_mr,
        ward=grievance.ward,
        latitude=grievance.latitude,
        longitude=grievance.longitude,
        citizen_id=grievance.citizen_id,
        citizen_name=grievance.citizen_name,
        phone=grievance.phone,
        submitted_date=grievance.submitted_date,
        resolved_date=grievance.resolved_date,
        officer_notes=grievance.officer_notes,
        auto_classified=grievance.auto_classified,
        village_id=grievance.village_id,
        request_type=grievance.request_type or "service",
        request_type_mr=REQUEST_TYPE_MR.get(grievance.request_type or "service"),
        requested_quantity=grievance.requested_quantity,
        project_id=grievance.project_id,
        similar_count=similar_count,
        citizen_feedback=grievance.citizen_feedback,
        feedback_note=grievance.feedback_note,
        feedback_at=grievance.feedback_at,
    )


def grievance_out(grievance: Grievance, similar_count: int = 0) -> GrievanceOut:
    return GrievanceOut(**_grievance_fields(grievance, similar_count))


def grievance_detail(grievance: Grievance, similar_count: int = 0) -> GrievanceDetail:
    return GrievanceDetail(
        **_grievance_fields(grievance, similar_count),
        events=[GrievanceEventOut.model_validate(e) for e in grievance.events],
        project=project_brief(grievance.project) if grievance.project else None,
    )
