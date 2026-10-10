"""add known devices and login challenges

Revision ID: f1b8d4e6a2c0
Revises: e5a2c9f1b7d3
Create Date: 2026-10-10

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'f1b8d4e6a2c0'
down_revision: Union[str, None] = 'e5a2c9f1b7d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'known_devices',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('user_id', sa.String(length=64), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('device_hash', sa.String(length=64), nullable=False),
        sa.Column('label', sa.String(length=200)),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('user_id', 'device_hash', name='uq_known_device'),
    )
    op.create_index('ix_known_devices_user_id', 'known_devices', ['user_id'])
    op.create_table(
        'login_challenges',
        sa.Column('id', sa.String(length=64), primary_key=True),
        sa.Column('user_id', sa.String(length=64), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('device_hash', sa.String(length=64), nullable=False),
        sa.Column('label', sa.String(length=200)),
        sa.Column('ip', sa.String(length=64)),
        sa.Column('poll_hash', sa.String(length=64), nullable=False),
        sa.Column('decision_hash', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_login_challenges_user_id', 'login_challenges', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_login_challenges_user_id', table_name='login_challenges')
    op.drop_table('login_challenges')
    op.drop_index('ix_known_devices_user_id', table_name='known_devices')
    op.drop_table('known_devices')
