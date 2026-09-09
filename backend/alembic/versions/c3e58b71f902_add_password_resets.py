"""add password_resets and users.tokens_valid_from

Revision ID: c3e58b71f902
Revises: a7f1c2e9d340
Create Date: 2026-09-09 11:48:22.503914
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c3e58b71f902'
down_revision: Union[str, None] = 'a7f1c2e9d340'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "password_resets",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        # bcrypt of the code, never the code itself.
        sa.Column("hashed_code", sa.String(length=255), nullable=False),
        sa.Column("issued_by_id", sa.String(length=64), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["issued_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_password_resets_user_id"), "password_resets", ["user_id"]
    )
    op.create_index(
        op.f("ix_password_resets_created_at"), "password_resets", ["created_at"]
    )

    # Tokens issued before this are refused, which is what makes a reset end the
    # session of whoever already had the account. Null on every existing row:
    # nothing has been revoked yet, so nothing should be invalidated by this
    # migration running.
    with op.batch_alter_table("users") as batch:
        batch.add_column(
            sa.Column("tokens_valid_from", sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("tokens_valid_from")

    op.drop_index(op.f("ix_password_resets_created_at"), table_name="password_resets")
    op.drop_index(op.f("ix_password_resets_user_id"), table_name="password_resets")
    op.drop_table("password_resets")
