"""add aadhaar to citizens

Revision ID: e5a2c9f1b7d3
Revises: d91b04a7c655
Create Date: 2026-10-10

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'e5a2c9f1b7d3'
down_revision: Union[str, None] = 'd91b04a7c655'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('citizens', sa.Column('aadhaar_hash', sa.String(length=64), nullable=True))
    op.add_column('citizens', sa.Column('aadhaar_last4', sa.String(length=4), nullable=True))
    op.create_index('ix_citizens_aadhaar_hash', 'citizens', ['aadhaar_hash'], unique=True)

    # Give the already-seeded synthetic residents their demo Aadhaar numbers,
    # so an existing database does not need re-seeding to show Aadhaar sign-in.
    from app.seed import demo_aadhaar
    from app.core.security import aadhaar_digest

    conn = op.get_bind()
    for (cid,) in conn.execute(sa.text("SELECT id FROM citizens")).fetchall():
        number = demo_aadhaar(cid)
        if number:
            conn.execute(
                sa.text("UPDATE citizens SET aadhaar_hash = :h, aadhaar_last4 = :l WHERE id = :id"),
                {"h": aadhaar_digest(number), "l": number[-4:], "id": cid},
            )


def downgrade() -> None:
    op.drop_index('ix_citizens_aadhaar_hash', table_name='citizens')
    op.drop_column('citizens', 'aadhaar_last4')
    op.drop_column('citizens', 'aadhaar_hash')
