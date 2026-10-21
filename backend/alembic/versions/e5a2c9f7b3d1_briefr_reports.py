"""briefr: agent reports and their findings

Revision ID: e5a2c9f7b3d1
Revises: b7d3f1a9c5e2
Create Date: 2026-10-18 20:00:00.000000

Two new tables for the briefr module (docs/adr/0044-briefr-agent-reports.md): `briefr_reports`,
one per report file an agent committed, and `briefr_report_items`, the findings in it. Guarded,
because app.main's create_all may have built them already.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'e5a2c9f7b3d1'
down_revision: str | None = 'b7d3f1a9c5e2'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table('briefr_reports'):
        op.create_table(
            'briefr_reports',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('source_path', sa.String(300), nullable=False, unique=True),
            sa.Column('content_hash', sa.String(64), nullable=False),
            sa.Column('agent', sa.String(64), nullable=False),
            sa.Column('run_at', sa.DateTime(), nullable=False),
            sa.Column('title', sa.String(200), nullable=False),
            sa.Column('summary', sa.Text(), nullable=True),
            sa.Column('body', sa.Text(), nullable=False),
            sa.Column('attention', sa.Enum('ACT', 'WATCH', 'INFO', name='briefrattention'), nullable=False),
            sa.Column('read_at', sa.DateTime(), nullable=True),
            sa.Column('archived_at', sa.DateTime(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index('ix_briefr_reports_agent', 'briefr_reports', ['agent'])
        op.create_index('ix_briefr_reports_run_at', 'briefr_reports', ['run_at'])
    if not inspector.has_table('briefr_report_items'):
        op.create_table(
            'briefr_report_items',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('report_id', sa.Integer(), sa.ForeignKey('briefr_reports.id'), nullable=False),
            sa.Column('sort_order', sa.Integer(), nullable=False),
            sa.Column('symbol', sa.String(32), nullable=True),
            sa.Column('asset_id', sa.Integer(), sa.ForeignKey('assets.id'), nullable=True),
            sa.Column('verdict', sa.Enum('ACT', 'WATCH', 'IGNORE', name='briefrverdict'), nullable=False),
            sa.Column('headline', sa.String(300), nullable=False),
            sa.Column('detail', sa.Text(), nullable=True),
            sa.Column('sources', sa.Text(), nullable=False),
        )
        op.create_index('ix_briefr_report_items_report_id', 'briefr_report_items', ['report_id'])
        op.create_index('ix_briefr_report_items_asset_id', 'briefr_report_items', ['asset_id'])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table('briefr_report_items'):
        op.drop_table('briefr_report_items')
    if inspector.has_table('briefr_reports'):
        op.drop_table('briefr_reports')
