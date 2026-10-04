"""generalize gripr portfolio bridge to multiple links

Revision ID: a5b64c0f3d52
Revises: d4f7a2c8e1b5
Create Date: 2026-09-26 00:00:00.000000

Generalizes the gripr<->gainr bridge (ADR 0014) from a single hardcoded link
(`pefi_settings.portfolio_account_id`, always pointed at gainr's Main portfolio) to a
`pefi_portfolio_links` table of (account_id, portfolio_id) pairs, so a second gripr account can
mirror a second gainr portfolio the same way the first one already mirrors Main. See
docs/adr/0021.

The existing single link, if any, is carried over as a row pointing at Main, so this is a no-op
for what's already there. Guarded with an inspector for the same reason every migration since
the logo one is.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'a5b64c0f3d52'
down_revision: str | None = 'd4f7a2c8e1b5'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

MAIN_PORTFOLIO_NAME = "Main"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = inspector.get_table_names()

    if 'pefi_portfolio_links' not in existing_tables:
        op.create_table(
            'pefi_portfolio_links',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('account_id', sa.Integer(), nullable=False),
            sa.Column('portfolio_id', sa.Integer(), nullable=False),
        )
        op.create_index('ix_pefi_portfolio_links_account_id', 'pefi_portfolio_links', ['account_id'], unique=True)
        op.create_index('ix_pefi_portfolio_links_portfolio_id', 'pefi_portfolio_links', ['portfolio_id'], unique=True)
        inspector = sa.inspect(bind)

    settings_columns = [c['name'] for c in inspector.get_columns('pefi_settings')]
    if 'portfolio_account_id' in settings_columns:
        settings = sa.table(
            'pefi_settings', sa.column('id', sa.Integer), sa.column('portfolio_account_id', sa.Integer),
        )
        account_id = bind.execute(sa.select(settings.c.portfolio_account_id)).scalar()
        if account_id is not None:
            portfolios = sa.table('portfolios', sa.column('id', sa.Integer), sa.column('name', sa.String))
            main_id = bind.execute(sa.select(portfolios.c.id).where(portfolios.c.name == MAIN_PORTFOLIO_NAME)).scalar()
            if main_id is not None:
                links = sa.table(
                    'pefi_portfolio_links', sa.column('account_id', sa.Integer), sa.column('portfolio_id', sa.Integer),
                )
                bind.execute(links.insert().values(account_id=account_id, portfolio_id=main_id))

        with op.batch_alter_table('pefi_settings') as batch_op:
            batch_op.drop_column('portfolio_account_id')


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    settings_columns = [c['name'] for c in inspector.get_columns('pefi_settings')]
    if 'portfolio_account_id' not in settings_columns:
        with op.batch_alter_table('pefi_settings') as batch_op:
            batch_op.add_column(sa.Column('portfolio_account_id', sa.Integer(), nullable=True))

        if 'pefi_portfolio_links' in inspector.get_table_names():
            portfolios = sa.table('portfolios', sa.column('id', sa.Integer), sa.column('name', sa.String))
            main_id = bind.execute(sa.select(portfolios.c.id).where(portfolios.c.name == MAIN_PORTFOLIO_NAME)).scalar()
            if main_id is not None:
                links = sa.table(
                    'pefi_portfolio_links', sa.column('account_id', sa.Integer), sa.column('portfolio_id', sa.Integer),
                )
                account_id = bind.execute(sa.select(links.c.account_id).where(links.c.portfolio_id == main_id)).scalar()
                if account_id is not None:
                    settings = sa.table(
                        'pefi_settings', sa.column('id', sa.Integer), sa.column('portfolio_account_id', sa.Integer),
                    )
                    bind.execute(settings.update().values(portfolio_account_id=account_id))

    if 'pefi_portfolio_links' in inspector.get_table_names():
        existing_indexes = {ix['name'] for ix in inspector.get_indexes('pefi_portfolio_links')}
        for name in ('ix_pefi_portfolio_links_account_id', 'ix_pefi_portfolio_links_portfolio_id'):
            if name in existing_indexes:
                op.drop_index(name, table_name='pefi_portfolio_links')
        op.drop_table('pefi_portfolio_links')
