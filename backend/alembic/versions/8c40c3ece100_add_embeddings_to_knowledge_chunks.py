"""add embeddings to knowledge chunks

Revision ID: 8c40c3ece100
Revises: b4d9b6474099
Create Date: 2026-08-31 05:57:37.021560
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '8c40c3ece100'
down_revision: Union[str, None] = 'b4d9b6474099'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # batch_alter_table because SQLite cannot ALTER a constraint in place; it
    # rebuilds the table instead. The constraint is named explicitly so the
    # downgrade can find it — an auto-named one cannot be dropped on SQLite.
    with op.batch_alter_table("knowledge_chunks") as batch:
        batch.add_column(sa.Column("embedding", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("embedding_model", sa.String(length=80), nullable=True))
        batch.add_column(sa.Column("village_id", sa.String(length=64), nullable=True))
        batch.create_foreign_key(
            "fk_knowledge_chunks_village_id",
            "villages",
            ["village_id"],
            ["id"],
            ondelete="CASCADE",
        )

    op.create_index(
        op.f("ix_knowledge_chunks_village_id"),
        "knowledge_chunks",
        ["village_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_knowledge_chunks_village_id"), table_name="knowledge_chunks")
    with op.batch_alter_table("knowledge_chunks") as batch:
        batch.drop_constraint("fk_knowledge_chunks_village_id", type_="foreignkey")
        batch.drop_column("village_id")
        batch.drop_column("embedding_model")
        batch.drop_column("embedding")
