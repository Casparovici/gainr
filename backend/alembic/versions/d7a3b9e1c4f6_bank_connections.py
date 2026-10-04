"""gripr: from one ING connection to one connection per bank

Revision ID: d7a3b9e1c4f6
Revises: c5e1a7d3f9b2
Create Date: 2026-10-02 15:00:00.000000

The ING sync (c5e1a7d3f9b2) generalises to any bank Enable Banking reaches, starting with
Trade Republic. ing_sync_settings' single row becomes the ING row of a new bank_connections
table, next to a Trade Republic row (off, not connected); the other three tables are renamed
ing_* -> bank_*, accounts gain the connection they belong to, and handled-entry references get
their bank's prefix ("ing:<entry reference>"), the same string the booked gripr row carries as
source_ref. Everything already set up for ING -- consent, account mapping, rules, handled
entries -- carries over unchanged. See docs/adr/0029-ing-transactions-into-gripr.md.

Guarded with an inspector for the same reason every migration since the logo one is.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'd7a3b9e1c4f6'
down_revision: str | None = 'c5e1a7d3f9b2'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

ING_ID = 1
TRADE_REPUBLIC_ID = 2
SETTINGS_COLUMNS = ('enabled', 'since', 'session_id', 'valid_until', 'pending_state', 'last_synced_at', 'last_error')


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    # app.main runs create_all at startup, so a server that started on the new models before
    # this ran (a dev server reloading) has already made the bank_* tables -- empty. Each step
    # therefore either renames the old table or, when the new one already exists, moves its rows
    # across; seeding never assumes the table was just created.
    if not inspector.has_table('bank_connections'):
        op.create_table(
            'bank_connections',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('aspsp_name', sa.String(80), nullable=False),
            sa.Column('aspsp_country', sa.String(2), nullable=False),
            sa.Column('source_prefix', sa.String(8), nullable=False, unique=True),
            sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('since', sa.Date(), nullable=True),
            sa.Column('session_id', sa.String(64), nullable=True),
            sa.Column('valid_until', sa.DateTime(), nullable=True),
            sa.Column('pending_state', sa.String(64), nullable=True),
            sa.Column('last_synced_at', sa.DateTime(), nullable=True),
            sa.Column('last_error', sa.String(300), nullable=True),
        )
    op.execute(
        "INSERT OR IGNORE INTO bank_connections (id, aspsp_name, aspsp_country, source_prefix, enabled) VALUES "
        f"({ING_ID}, 'ING', 'NL', 'ing', 0), ({TRADE_REPUBLIC_ID}, 'Trade Republic', 'NL', 'tr', 0)"
    )
    if inspector.has_table('ing_sync_settings'):
        assignments = ", ".join(f"{c} = (SELECT {c} FROM ing_sync_settings WHERE id = 1)" for c in SETTINGS_COLUMNS)
        op.execute(f"UPDATE bank_connections SET {assignments} WHERE id = {ING_ID} AND EXISTS (SELECT 1 FROM ing_sync_settings WHERE id = 1)")
        op.drop_table('ing_sync_settings')

    if inspector.has_table('ing_sync_accounts'):
        if not inspector.has_table('bank_sync_accounts'):
            op.rename_table('ing_sync_accounts', 'bank_sync_accounts')
            with op.batch_alter_table('bank_sync_accounts') as batch_op:
                batch_op.add_column(sa.Column('connection_id', sa.Integer(), nullable=False, server_default=str(ING_ID)))
                batch_op.create_foreign_key('fk_bank_sync_accounts_connection', 'bank_connections', ['connection_id'], ['id'], ondelete='CASCADE')
                batch_op.create_index('ix_bank_sync_accounts_connection_id', ['connection_id'])
        else:
            op.execute(
                "INSERT OR IGNORE INTO bank_sync_accounts (iban, connection_id, eb_uid, product, holder_name, gripr_account_id) "
                f"SELECT iban, {ING_ID}, eb_uid, product, holder_name, gripr_account_id FROM ing_sync_accounts"
            )
            op.drop_table('ing_sync_accounts')

    if inspector.has_table('ing_counterparty_rules'):
        if not inspector.has_table('bank_counterparty_rules'):
            op.rename_table('ing_counterparty_rules', 'bank_counterparty_rules')
        else:
            op.execute(
                "INSERT OR IGNORE INTO bank_counterparty_rules (id, iban, text_contains, gripr_account_id) "
                "SELECT id, iban, text_contains, gripr_account_id FROM ing_counterparty_rules"
            )
            op.drop_table('ing_counterparty_rules')

    if inspector.has_table('ing_synced_transactions'):
        if not inspector.has_table('bank_synced_transactions'):
            op.rename_table('ing_synced_transactions', 'bank_synced_transactions')
        else:
            op.execute(
                "INSERT OR IGNORE INTO bank_synced_transactions "
                "(reference, iban, transacted_on, synced_at, outcome, gripr_transaction_id, recurring_id) "
                "SELECT reference, iban, transacted_on, synced_at, outcome, gripr_transaction_id, recurring_id FROM ing_synced_transactions"
            )
            op.drop_table('ing_synced_transactions')
        op.execute("UPDATE bank_synced_transactions SET reference = 'ing:' || reference WHERE reference NOT LIKE '%:%'")


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table('bank_synced_transactions'):
        op.execute("DELETE FROM bank_synced_transactions WHERE reference NOT LIKE 'ing:%'")
        op.execute("UPDATE bank_synced_transactions SET reference = substr(reference, 5)")
        op.rename_table('bank_synced_transactions', 'ing_synced_transactions')
    if inspector.has_table('bank_counterparty_rules'):
        op.rename_table('bank_counterparty_rules', 'ing_counterparty_rules')
    if inspector.has_table('bank_sync_accounts'):
        op.execute(f"DELETE FROM bank_sync_accounts WHERE connection_id != {ING_ID}")
        with op.batch_alter_table('bank_sync_accounts') as batch_op:
            batch_op.drop_index('ix_bank_sync_accounts_connection_id')
            batch_op.drop_constraint('fk_bank_sync_accounts_connection', type_='foreignkey')
            batch_op.drop_column('connection_id')
        op.rename_table('bank_sync_accounts', 'ing_sync_accounts')
    if inspector.has_table('bank_connections'):
        op.create_table(
            'ing_sync_settings',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('since', sa.Date(), nullable=True),
            sa.Column('session_id', sa.String(64), nullable=True),
            sa.Column('valid_until', sa.DateTime(), nullable=True),
            sa.Column('pending_state', sa.String(64), nullable=True),
            sa.Column('last_synced_at', sa.DateTime(), nullable=True),
            sa.Column('last_error', sa.String(300), nullable=True),
        )
        columns = ", ".join(SETTINGS_COLUMNS)
        op.execute(f"INSERT INTO ing_sync_settings (id, {columns}) SELECT 1, {columns} FROM bank_connections WHERE id = {ING_ID}")
        op.drop_table('bank_connections')
