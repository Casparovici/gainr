"""add gainr portfolios

Revision ID: d4f7a2c8e1b5
Revises: c1d5f8a2e6b4
Create Date: 2026-09-24 00:00:00.000000

Introduces multi-portfolio support for gainr (see docs/adr/0019): a new `portfolios` table, a
required `portfolio_id` on every transaction, and per-portfolio target-weight judgments
(`portfolio_asset_targets` replaces `assets.target_weight_pct`; `portfolio_settings` stops being
a hardcoded singleton and gets a `portfolio_id` column instead). Every existing row is backfilled
onto one seeded "Main" portfolio, so this is a no-op change in what the app shows -- only new
portfolios created after this migration add anything.

Guarded with an inspector for the same reason every migration since the logo one is: app.main
calls Base.metadata.create_all on startup, so on a database already booted against this code the
new tables/columns exist before this migration runs. This one also touches real data (a backfill
and a column drop) -- back up backend/portfolio.db before running it against real history.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'd4f7a2c8e1b5'
down_revision: str | None = 'c1d5f8a2e6b4'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

MAIN_PORTFOLIO_NAME = "Main"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if 'portfolios' not in existing_tables:
        op.create_table(
            'portfolios',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('name', sa.String(120), nullable=False),
            sa.Column('is_archived', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        )
        inspector = sa.inspect(bind)

    portfolios = sa.table(
        'portfolios', sa.column('id', sa.Integer), sa.column('name', sa.String),
        sa.column('is_archived', sa.Boolean), sa.column('sort_order', sa.Integer),
    )
    main_id = bind.execute(sa.select(portfolios.c.id).where(portfolios.c.name == MAIN_PORTFOLIO_NAME)).scalar()
    if main_id is None:
        bind.execute(portfolios.insert().values(name=MAIN_PORTFOLIO_NAME, is_archived=False, sort_order=0))
        main_id = bind.execute(sa.select(portfolios.c.id).where(portfolios.c.name == MAIN_PORTFOLIO_NAME)).scalar()

    # -- transactions.portfolio_id --------------------------------------------------------
    txn_columns = [c['name'] for c in inspector.get_columns('transactions')]
    if 'portfolio_id' not in txn_columns:
        # A plain column, not a DB-level FK -- this app doesn't rely on DB-enforced FK
        # integrity (see e.g. pefi_categories.linked_loan_account_id). SQLite also can't add
        # a NOT NULL column with no default to a table that already has rows, so this is added
        # nullable and backfilled immediately below; the ORM model declares it NOT NULL and
        # every write path always supplies it, same convention as elsewhere in this app.
        op.add_column('transactions', sa.Column('portfolio_id', sa.Integer(), nullable=True))
        transactions = sa.table('transactions', sa.column('id', sa.Integer), sa.column('portfolio_id', sa.Integer))
        bind.execute(transactions.update().where(transactions.c.portfolio_id.is_(None)).values(portfolio_id=main_id))
        op.create_index('ix_transactions_portfolio_id', 'transactions', ['portfolio_id'])

    # -- portfolio_asset_targets, replacing assets.target_weight_pct ----------------------
    if 'portfolio_asset_targets' not in existing_tables:
        op.create_table(
            'portfolio_asset_targets',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('portfolio_id', sa.Integer(), nullable=False),
            sa.Column('asset_id', sa.Integer(), nullable=False),
            sa.Column('target_weight_pct', sa.Numeric(5, 2), nullable=False),
            sa.UniqueConstraint('portfolio_id', 'asset_id', name='uq_portfolio_asset_target'),
        )
        op.create_index('ix_portfolio_asset_targets_portfolio_id', 'portfolio_asset_targets', ['portfolio_id'])
        op.create_index('ix_portfolio_asset_targets_asset_id', 'portfolio_asset_targets', ['asset_id'])

    asset_columns = [c['name'] for c in inspector.get_columns('assets')]
    if 'target_weight_pct' in asset_columns:
        assets = sa.table('assets', sa.column('id', sa.Integer), sa.column('target_weight_pct', sa.Numeric))
        targets = sa.table(
            'portfolio_asset_targets', sa.column('portfolio_id', sa.Integer),
            sa.column('asset_id', sa.Integer), sa.column('target_weight_pct', sa.Numeric),
        )
        rows = bind.execute(
            sa.select(assets.c.id, assets.c.target_weight_pct).where(assets.c.target_weight_pct.is_not(None))
        ).all()
        for asset_id, weight in rows:
            bind.execute(targets.insert().values(portfolio_id=main_id, asset_id=asset_id, target_weight_pct=weight))

        with op.batch_alter_table('assets') as batch_op:
            batch_op.drop_column('target_weight_pct')

    # -- portfolio_settings.portfolio_id, retiring the SETTINGS_ID=1 singleton ------------
    ps_columns = [c['name'] for c in inspector.get_columns('portfolio_settings')]
    if 'portfolio_id' not in ps_columns:
        op.add_column('portfolio_settings', sa.Column('portfolio_id', sa.Integer(), nullable=True))
        settings = sa.table('portfolio_settings', sa.column('id', sa.Integer), sa.column('portfolio_id', sa.Integer))
        bind.execute(settings.update().where(settings.c.portfolio_id.is_(None)).values(portfolio_id=main_id))
        op.create_index('ix_portfolio_settings_portfolio_id', 'portfolio_settings', ['portfolio_id'], unique=True)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Indexes on a column being dropped are removed explicitly first -- SQLite's batch-copy
    # recreate otherwise tries to recreate the index on the new table before the column it
    # references exists there, which fails.
    ps_columns = [c['name'] for c in inspector.get_columns('portfolio_settings')]
    if 'portfolio_id' in ps_columns:
        existing_indexes = {ix['name'] for ix in inspector.get_indexes('portfolio_settings')}
        if 'ix_portfolio_settings_portfolio_id' in existing_indexes:
            op.drop_index('ix_portfolio_settings_portfolio_id', table_name='portfolio_settings')
        with op.batch_alter_table('portfolio_settings') as batch_op:
            batch_op.drop_column('portfolio_id')

    asset_columns = [c['name'] for c in inspector.get_columns('assets')]
    if 'target_weight_pct' not in asset_columns:
        with op.batch_alter_table('assets') as batch_op:
            batch_op.add_column(sa.Column('target_weight_pct', sa.Numeric(5, 2), nullable=True))

    if 'portfolio_asset_targets' in inspector.get_table_names():
        op.drop_table('portfolio_asset_targets')

    txn_columns = [c['name'] for c in inspector.get_columns('transactions')]
    if 'portfolio_id' in txn_columns:
        existing_indexes = {ix['name'] for ix in inspector.get_indexes('transactions')}
        if 'ix_transactions_portfolio_id' in existing_indexes:
            op.drop_index('ix_transactions_portfolio_id', table_name='transactions')
        with op.batch_alter_table('transactions') as batch_op:
            batch_op.drop_column('portfolio_id')

    if 'portfolios' in inspector.get_table_names():
        op.drop_table('portfolios')
