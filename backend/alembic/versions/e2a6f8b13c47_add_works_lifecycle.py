"""add the works lifecycle: stages, a budget ledger and what links to them

Revision ID: e2a6f8b13c47
Revises: d91b04a7c655
Create Date: 2026-10-04 11:32:17.640381
"""
from datetime import datetime, timedelta, timezone
from typing import Sequence, Union
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision: str = 'e2a6f8b13c47'
down_revision: Union[str, None] = 'd91b04a7c655'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """A project stops being a name, a percentage and two totals.

    It gets a stage, a ledger of dated money entries, and a history; complaints
    can point at the work they led to; and the asset register can say which work
    built a thing and how many of it.

    The NOT NULL columns carry server defaults so they can be added to tables
    that already hold rows. Every work that exists when this runs is then given
    the ledger entries that add up to the two totals it was recorded with, so
    no work is left holding its money in the old form.
    """
    # ── The ledger ───────────────────────────────────────────────────────────
    op.create_table(
        "budget_entries",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        # 'estimate' | 'requested' | 'approved' | 'received' | 'spent'
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("amount", sa.Numeric(precision=15, scale=2), nullable=False),
        # When it happened, which is not always when it was typed in.
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("funding_source", sa.String(length=30), nullable=True),
        sa.Column("reference", sa.String(length=120), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.String(length=64), nullable=True),
        sa.Column("created_by_name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_budget_entries_project_id"), "budget_entries", ["project_id"])
    op.create_index(op.f("ix_budget_entries_entry_date"), "budget_entries", ["entry_date"])
    op.create_index(op.f("ix_budget_entries_created_at"), "budget_entries", ["created_at"])
    # "The latest approval for this work" and "everything spent on it" are the
    # two reads every project response makes.
    op.create_index(
        "ix_budget_entries_project_kind", "budget_entries", ["project_id", "kind"]
    )

    # ── A work's history ─────────────────────────────────────────────────────
    op.create_table(
        "project_events",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=30), nullable=False),
        sa.Column("from_stage", sa.String(length=30), nullable=True),
        sa.Column("to_stage", sa.String(length=30), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("note_mr", sa.Text(), nullable=True),
        sa.Column("actor_id", sa.String(length=64), nullable=True),
        sa.Column("actor_name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_project_events_project_id"), "project_events", ["project_id"])
    op.create_index(op.f("ix_project_events_created_at"), "project_events", ["created_at"])

    # ── Projects ─────────────────────────────────────────────────────────────
    # Every existing work has started — there was no way to record one that had
    # not — so 'in_progress' is the true default for the rows already here.
    op.add_column("projects", sa.Column(
        "stage", sa.String(length=30), nullable=False, server_default="in_progress"))
    op.add_column("projects", sa.Column(
        "stage_changed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("projects", sa.Column("held_from_stage", sa.String(length=30), nullable=True))
    op.add_column("projects", sa.Column("category", sa.String(length=60), nullable=True))
    op.add_column("projects", sa.Column("units_planned", sa.Integer(), nullable=True))
    op.add_column("projects", sa.Column(
        "units_done", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("projects", sa.Column("unit_label", sa.String(length=60), nullable=True))
    op.add_column("projects", sa.Column("unit_label_mr", sa.String(length=60), nullable=True))
    op.add_column("projects", sa.Column("asset_type", sa.String(length=40), nullable=True))
    op.add_column("projects", sa.Column("funding_source", sa.String(length=30), nullable=True))
    op.add_column("projects", sa.Column("decision_note", sa.Text(), nullable=True))
    op.add_column("projects", sa.Column("sabha_meeting_id", sa.String(length=64), nullable=True))
    op.create_index(op.f("ix_projects_stage"), "projects", ["stage"])
    with op.batch_alter_table("projects") as batch:
        batch.create_foreign_key(
            "fk_projects_sabha_meeting_id", "sabha_meetings",
            ["sabha_meeting_id"], ["id"], ondelete="SET NULL",
        )

    # ── Grievances ───────────────────────────────────────────────────────────
    # Existing complaints are all repairs as far as anyone recorded; an officer
    # can change that on any of them.
    op.add_column("grievances", sa.Column(
        "request_type", sa.String(length=20), nullable=False, server_default="service"))
    op.add_column("grievances", sa.Column("requested_quantity", sa.Integer(), nullable=True))
    op.add_column("grievances", sa.Column("project_id", sa.String(length=64), nullable=True))
    op.add_column("grievances", sa.Column("citizen_feedback", sa.String(length=20), nullable=True))
    op.add_column("grievances", sa.Column("feedback_note", sa.Text(), nullable=True))
    op.add_column("grievances", sa.Column(
        "feedback_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index(op.f("ix_grievances_request_type"), "grievances", ["request_type"])
    op.create_index(op.f("ix_grievances_project_id"), "grievances", ["project_id"])
    with op.batch_alter_table("grievances") as batch:
        batch.create_foreign_key(
            "fk_grievances_project_id", "projects",
            ["project_id"], ["id"], ondelete="SET NULL",
        )

    # ── The asset register ───────────────────────────────────────────────────
    op.add_column("facilities", sa.Column(
        "quantity", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("facilities", sa.Column("project_id", sa.String(length=64), nullable=True))
    op.add_column("facilities", sa.Column("installed_on", sa.Date(), nullable=True))
    op.create_index(op.f("ix_facilities_project_id"), "facilities", ["project_id"])
    with op.batch_alter_table("facilities") as batch:
        batch.create_foreign_key(
            "fk_facilities_project_id", "projects",
            ["project_id"], ["id"], ondelete="SET NULL",
        )

    _open_ledgers()


def _open_ledgers() -> None:
    """Give each existing work the entries that add up to its two totals.

    Mirrors `services.works.open_ledger`, written out here rather than imported
    so this migration keeps doing what it does today however that function is
    changed later.

    The sanctioned amount becomes both an approval and a receipt. The old
    record could not tell the two apart, and treating the sanction as available
    is what keeps "remaining" on every screen equal to what it showed before
    this ran. `projects.budget` and `projects.utilized` are left exactly as they
    were: afterwards they are the totals of these entries, which is the same
    numbers.
    """
    bind = op.get_bind()

    projects = sa.table(
        "projects",
        sa.column("id", sa.String),
        sa.column("budget", sa.Numeric(15, 2)),
        sa.column("utilized", sa.Numeric(15, 2)),
        sa.column("status", sa.String),
        sa.column("stage", sa.String),
        sa.column("stage_changed_at", sa.DateTime(timezone=True)),
        sa.column("start_date", sa.Date),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    entries = sa.table(
        "budget_entries",
        sa.column("id", sa.String),
        sa.column("project_id", sa.String),
        sa.column("kind", sa.String),
        sa.column("amount", sa.Numeric(15, 2)),
        sa.column("entry_date", sa.Date),
        sa.column("note", sa.Text),
        sa.column("created_by_name", sa.String),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )

    now = datetime.now(timezone.utc)
    rows = bind.execute(sa.select(
        projects.c.id, projects.c.budget, projects.c.utilized, projects.c.status,
        projects.c.start_date, projects.c.created_at, projects.c.updated_at,
    )).fetchall()

    new_entries: list[dict] = []
    for row in rows:
        # The best date on record for when the money was there: the day the
        # work started if that was noted, else the day it was entered.
        on = row.start_date or (row.created_at.date() if row.created_at else now.date())
        budget = float(row.budget or 0)
        used = float(row.utilized or 0)
        for kind, amount in (("approved", budget), ("received", budget), ("spent", used)):
            if amount > 0:
                new_entries.append({
                    "id": f"bud_{uuid4().hex[:12]}",
                    "project_id": row.id,
                    "kind": kind,
                    "amount": amount,
                    "entry_date": on,
                    "note": "Opening balance carried over from the project record.",
                    "created_by_name": "Carried over",
                    # A microsecond apart, so the three read back in this order.
                    "created_at": now + timedelta(microseconds=len(new_entries)),
                })

        bind.execute(
            projects.update()
            .where(projects.c.id == row.id)
            .values(
                stage="completed" if row.status == "Completed" else "in_progress",
                # When the row last changed is the nearest thing on record to
                # when it reached the state it is in.
                stage_changed_at=row.updated_at or row.created_at or now,
            )
        )

    if new_entries:
        op.bulk_insert(entries, new_entries)


def downgrade() -> None:
    """Back to two totals per work.

    `projects.budget` and `projects.utilized` were kept in step with the ledger
    throughout, so the totals survive; the dated entries behind them, the stage
    history, the complaint links and the citizen feedback do not.

    Works that never started are deleted. The old model has three statuses —
    Ongoing, Delayed, Completed — and no way to say "proposed", "awaiting
    budget" or "not approved"; left in place, such a row fails the old API's
    response validation and takes the whole project list down with it. A work
    that had started and was then put on hold is kept, as Delayed, which is the
    nearest thing the old model can say.
    """
    bind = op.get_bind()
    projects = sa.table(
        "projects",
        sa.column("stage", sa.String),
        sa.column("held_from_stage", sa.String),
        sa.column("status", sa.String),
        sa.column("status_mr", sa.String),
    )
    held_after_starting = sa.and_(
        projects.c.stage == "on_hold", projects.c.held_from_stage == "in_progress"
    )
    bind.execute(
        projects.update()
        .where(held_after_starting)
        .values(status="Delayed", status_mr="विलंब झालेला")
    )
    bind.execute(
        projects.delete().where(
            projects.c.stage.notin_(("in_progress", "completed")),
            # Spelled out with a COALESCE rather than as NOT(held_after_starting):
            # a null `held_from_stage` would make that NULL, and a row a WHERE
            # clause is unsure about is a row it leaves behind.
            sa.or_(
                projects.c.stage != "on_hold",
                sa.func.coalesce(projects.c.held_from_stage, "") != "in_progress",
            ),
        )
    )

    with op.batch_alter_table("facilities") as batch:
        batch.drop_constraint("fk_facilities_project_id", type_="foreignkey")
    op.drop_index(op.f("ix_facilities_project_id"), table_name="facilities")
    with op.batch_alter_table("facilities") as batch:
        batch.drop_column("installed_on")
        batch.drop_column("project_id")
        batch.drop_column("quantity")

    with op.batch_alter_table("grievances") as batch:
        batch.drop_constraint("fk_grievances_project_id", type_="foreignkey")
    op.drop_index(op.f("ix_grievances_project_id"), table_name="grievances")
    op.drop_index(op.f("ix_grievances_request_type"), table_name="grievances")
    with op.batch_alter_table("grievances") as batch:
        batch.drop_column("feedback_at")
        batch.drop_column("feedback_note")
        batch.drop_column("citizen_feedback")
        batch.drop_column("project_id")
        batch.drop_column("requested_quantity")
        batch.drop_column("request_type")

    with op.batch_alter_table("projects") as batch:
        batch.drop_constraint("fk_projects_sabha_meeting_id", type_="foreignkey")
    op.drop_index(op.f("ix_projects_stage"), table_name="projects")
    with op.batch_alter_table("projects") as batch:
        batch.drop_column("sabha_meeting_id")
        batch.drop_column("decision_note")
        batch.drop_column("funding_source")
        batch.drop_column("asset_type")
        batch.drop_column("unit_label_mr")
        batch.drop_column("unit_label")
        batch.drop_column("units_done")
        batch.drop_column("units_planned")
        batch.drop_column("category")
        batch.drop_column("held_from_stage")
        batch.drop_column("stage_changed_at")
        batch.drop_column("stage")

    op.drop_index(op.f("ix_project_events_created_at"), table_name="project_events")
    op.drop_index(op.f("ix_project_events_project_id"), table_name="project_events")
    op.drop_table("project_events")

    op.drop_index("ix_budget_entries_project_kind", table_name="budget_entries")
    op.drop_index(op.f("ix_budget_entries_created_at"), table_name="budget_entries")
    op.drop_index(op.f("ix_budget_entries_entry_date"), table_name="budget_entries")
    op.drop_index(op.f("ix_budget_entries_project_id"), table_name="budget_entries")
    op.drop_table("budget_entries")
