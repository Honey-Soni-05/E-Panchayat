"""add audit_events

Revision ID: d91b04a7c655
Revises: c3e58b71f902
Create Date: 2026-09-09 13:20:41.774903
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd91b04a7c655'
down_revision: Union[str, None] = 'c3e58b71f902'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("actor_id", sa.String(length=64), nullable=True),
        # Denormalised, so a row still says who acted after the account is
        # deleted and the foreign key above goes null.
        sa.Column("actor_email", sa.String(length=255), nullable=True),
        sa.Column("actor_role", sa.String(length=20), nullable=True),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("method", sa.String(length=10), nullable=False),
        sa.Column("path", sa.String(length=500), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(length=40), nullable=True),
        sa.Column("entity_id", sa.String(length=64), nullable=True),
        sa.Column("village_id", sa.String(length=64), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["village_id"], ["villages.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_events_actor_id"), "audit_events", ["actor_id"])
    op.create_index(op.f("ix_audit_events_action"), "audit_events", ["action"])
    op.create_index(op.f("ix_audit_events_entity_type"), "audit_events", ["entity_type"])
    op.create_index(op.f("ix_audit_events_entity_id"), "audit_events", ["entity_id"])
    op.create_index(op.f("ix_audit_events_village_id"), "audit_events", ["village_id"])
    op.create_index(op.f("ix_audit_events_created_at"), "audit_events", ["created_at"])
    # The two questions the trail exists to answer: everything that touched one
    # record, and everything one person did.
    op.create_index(
        "ix_audit_entity_time",
        "audit_events",
        ["entity_type", "entity_id", "created_at"],
    )
    op.create_index("ix_audit_actor_time", "audit_events", ["actor_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_audit_actor_time", table_name="audit_events")
    op.drop_index("ix_audit_entity_time", table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_created_at"), table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_village_id"), table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_entity_id"), table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_entity_type"), table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_action"), table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_actor_id"), table_name="audit_events")
    op.drop_table("audit_events")
