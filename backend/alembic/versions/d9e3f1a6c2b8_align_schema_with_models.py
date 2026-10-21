"""align the migrated schema with the models

Revision ID: d9e3f1a6c2b8
Revises: c4f8e2a7b1d6
Create Date: 2026-10-14 21:00:00.000000

A database built by `alembic upgrade head` had drifted from the one `Base.metadata.create_all`
builds from the models: foreign keys and NOT NULLs the models declare but no migration added,
two plain indexes the models declare unique (both columns were already unique through a table
constraint, so this changes the index, not what the data may hold), and index names left over from the ING-to-bank
rename. `alembic check` now reports no differences, and a test keeps it that way.

Every step is guarded with an inspector, because the real database may have any table in either
shape: app.main calls create_all on startup, so a table first created that way already matches
the models, and only migration-built tables need changing. Foreign keys are added with SQLite's
batch copy, which copies rows without checking them, so an orphaned row never blocks this.

Steps the data could break are skipped with a message rather than failing the deploy: a NOT NULL
whose column still holds NULLs (a gainr transaction or portfolio setting with no portfolio) stays
nullable, and so would a unique index over duplicates. created_at/updated_at NULLs are filled
with the current time first.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'd9e3f1a6c2b8'
down_revision: str | None = 'c4f8e2a7b1d6'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

# table -> [(column, referred table)]
FOREIGN_KEYS = {
    'grecipe_items': [('category_id', 'grecipe_categories')],
    'grecipe_list_items': [('list_id', 'grecipe_lists'), ('grocery_item_id', 'grecipe_items')],
    'grecipe_recipe_ingredients': [('recipe_id', 'grecipe_recipes'), ('grocery_item_id', 'grecipe_items')],
    'pefi_categories': [('linked_loan_account_id', 'pefi_accounts')],
    'pefi_portfolio_links': [('account_id', 'pefi_accounts'), ('portfolio_id', 'portfolios')],
    'pefi_savings_goals': [('account_id', 'pefi_accounts')],
    'portfolio_asset_targets': [('portfolio_id', 'portfolios'), ('asset_id', 'assets')],
    'portfolio_settings': [('portfolio_id', 'portfolios')],
    'transactions': [('portfolio_id', 'portfolios')],
}

# table -> columns the models declare NOT NULL
NOT_NULL = {
    'grecipe_lists': ['created_at', 'updated_at'],
    'grecipe_meal_plan': ['created_at', 'updated_at'],
    'grecipe_recipes': ['created_at', 'updated_at'],
    'pefi_bank_logos': ['fetched_at'],
    'picnic_session': ['updated_at'],
    'portfolios': ['created_at'],
    'portfolio_settings': ['portfolio_id'],
    'transactions': ['portfolio_id'],
}
TIMESTAMPS = {'created_at', 'updated_at', 'fetched_at'}

# (table, index, column): plain indexes the models declare unique
UNIQUE_INDEXES = [
    ('pefi_accounts', 'ix_pefi_accounts_name', 'name'),
    ('grecipe_meal_plan', 'ix_grecipe_meal_plan_date', 'date'),
]

# bank_synced_transactions kept the index names it had as ing_synced_transactions
RENAMED_INDEXES = [
    ('ix_ing_synced_transactions_gripr_transaction_id', 'ix_bank_synced_transactions_gripr_transaction_id', 'gripr_transaction_id'),
    ('ix_ing_synced_transactions_transacted_on', 'ix_bank_synced_transactions_transacted_on', 'transacted_on'),
]


def _fk_name(table: str, column: str) -> str:
    return f'fk_{table}_{column}'


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    for table in sorted(set(FOREIGN_KEYS) | set(NOT_NULL)):
        if table not in tables:
            continue
        columns = {c['name']: c for c in inspector.get_columns(table)}
        existing_fks = {tuple(fk['constrained_columns']) for fk in inspector.get_foreign_keys(table)}
        missing_fks = [
            (column, referred) for column, referred in FOREIGN_KEYS.get(table, [])
            if column in columns and (column,) not in existing_fks
        ]
        to_tighten = []
        for column in NOT_NULL.get(table, []):
            if column not in columns or not columns[column]['nullable']:
                continue
            if column in TIMESTAMPS:
                bind.execute(sa.text(f'UPDATE {table} SET {column} = CURRENT_TIMESTAMP WHERE {column} IS NULL'))
            nulls = bind.execute(sa.text(f'SELECT COUNT(*) FROM {table} WHERE {column} IS NULL')).scalar()
            if nulls:
                print(f'align schema: {table}.{column} has {nulls} NULL row(s); left nullable')
                continue
            to_tighten.append(columns[column])
        if not missing_fks and not to_tighten:
            continue
        with op.batch_alter_table(table) as batch:
            for column in to_tighten:
                batch.alter_column(column['name'], existing_type=column['type'], nullable=False)
            for column, referred in missing_fks:
                batch.create_foreign_key(_fk_name(table, column), referred, [column], ['id'])
        inspector = sa.inspect(bind)

    for table, index, column in UNIQUE_INDEXES:
        if table not in tables:
            continue
        indexes = {ix['name']: ix for ix in inspector.get_indexes(table)}
        if index in indexes and indexes[index]['unique']:
            continue
        duplicates = bind.execute(
            sa.text(f'SELECT COUNT(*) FROM (SELECT {column} FROM {table} GROUP BY {column} HAVING COUNT(*) > 1)')
        ).scalar()
        if duplicates:
            print(f'align schema: {table}.{column} has {duplicates} duplicated value(s); index left non-unique')
            continue
        if index in indexes:
            op.drop_index(index, table_name=table)
        op.create_index(index, table, [column], unique=True)

    if 'bank_synced_transactions' in tables:
        indexes = {ix['name'] for ix in inspector.get_indexes('bank_synced_transactions')}
        for old, new, column in RENAMED_INDEXES:
            if old in indexes:
                op.drop_index(old, table_name='bank_synced_transactions')
            if new not in indexes:
                op.create_index(new, 'bank_synced_transactions', [column])
        reference = next(c for c in inspector.get_columns('bank_synced_transactions') if c['name'] == 'reference')
        if getattr(reference['type'], 'length', None) != 80:
            with op.batch_alter_table('bank_synced_transactions') as batch:
                batch.alter_column('reference', existing_type=reference['type'], type_=sa.String(80))


def downgrade() -> None:
    # Only the renames are undone: the foreign keys, NOT NULLs and unique indexes describe what
    # the models (and so every create_all-built database) have always had.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'bank_synced_transactions' in inspector.get_table_names():
        indexes = {ix['name'] for ix in inspector.get_indexes('bank_synced_transactions')}
        for old, new, column in RENAMED_INDEXES:
            if new in indexes:
                op.drop_index(new, table_name='bank_synced_transactions')
            if old not in indexes:
                op.create_index(old, 'bank_synced_transactions', [column])
