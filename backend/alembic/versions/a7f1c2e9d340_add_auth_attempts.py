"""add auth_attempts for sign-in throttling and the auth audit trail

Revision ID: a7f1c2e9d340
Revises: 8c40c3ece100
Create Date: 2026-09-09 10:12:04.118207
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a7f1c2e9d340'
down_revision: Union[str, None] = '8c40c3ece100'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "auth_attempts",
        sa.Column("id", sa.String(length=64), nullable=False),
        # Stored as typed, whether or not any such account exists — throttling
        # only known accounts would make the throttle an enumeration oracle.
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("successful", sa.Boolean(), nullable=False,
                  server_default=sa.false()),
        sa.Column("outcome", sa.String(length=30), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_auth_attempts_email"), "auth_attempts", ["email"])
    op.create_index(op.f("ix_auth_attempts_ip"), "auth_attempts", ["ip"])
    op.create_index(
        op.f("ix_auth_attempts_created_at"), "auth_attempts", ["created_at"]
    )
    # The shape of the throttle's own query: recent failures for one email, and
    # recent failures from one source. Every sign-in runs both, and this table
    # is the only one that grows on unauthenticated traffic.
    op.create_index(
        "ix_auth_attempts_email_outcome_time",
        "auth_attempts",
        ["email", "outcome", "created_at"],
    )
    op.create_index(
        "ix_auth_attempts_ip_outcome_time",
        "auth_attempts",
        ["ip", "outcome", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_auth_attempts_ip_outcome_time", table_name="auth_attempts")
    op.drop_index("ix_auth_attempts_email_outcome_time", table_name="auth_attempts")
    op.drop_index(op.f("ix_auth_attempts_created_at"), table_name="auth_attempts")
    op.drop_index(op.f("ix_auth_attempts_ip"), table_name="auth_attempts")
    op.drop_index(op.f("ix_auth_attempts_email"), table_name="auth_attempts")
    op.drop_table("auth_attempts")
