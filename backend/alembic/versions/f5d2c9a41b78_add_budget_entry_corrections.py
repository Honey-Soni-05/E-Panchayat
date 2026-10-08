"""add corrections to budget entries

Revision ID: f5d2c9a41b78
Revises: e2a6f8b13c47
Create Date: 2026-10-04 17:52:40.118236
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f5d2c9a41b78'
down_revision: Union[str, None] = 'e2a6f8b13c47'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Let a wrong receipt or payment be put right without overwriting it.

    Receipts and payments add up, so a mistyped one could not be fixed by
    recording another — the total stayed wrong. A correction is a further row
    that points back at the entry it puts right and carries the difference, so
    the original figure, the corrected one, who changed it and why are all still
    on the record.

    Null on every existing row: nothing recorded so far is a correction.
    """
    op.add_column(
        "budget_entries", sa.Column("corrects_id", sa.String(length=64), nullable=True)
    )
    op.create_index(
        op.f("ix_budget_entries_corrects_id"), "budget_entries", ["corrects_id"]
    )
    with op.batch_alter_table("budget_entries") as batch:
        batch.create_foreign_key(
            "fk_budget_entries_corrects_id", "budget_entries",
            ["corrects_id"], ["id"], ondelete="SET NULL",
        )


def downgrade() -> None:
    """Drop the link, keep the rows.

    A correction is still an entry of the same kind carrying a difference, so
    every total stays exactly what it was. What is lost is which entry each one
    was correcting, which the older code never looked at.
    """
    with op.batch_alter_table("budget_entries") as batch:
        batch.drop_constraint("fk_budget_entries_corrects_id", type_="foreignkey")
    op.drop_index(op.f("ix_budget_entries_corrects_id"), table_name="budget_entries")
    with op.batch_alter_table("budget_entries") as batch:
        batch.drop_column("corrects_id")
