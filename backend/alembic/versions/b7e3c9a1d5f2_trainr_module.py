"""trainr: workouts (home gym, running, cycling), their exercise entries and an exercise catalogue

Revision ID: b7e3c9a1d5f2
Revises: a3d8f2c6b9e4
Create Date: 2026-10-12 12:00:00.000000

See docs/adr/0037-trainr-module.md. Guarded with an inspector because app.main runs
Base.metadata.create_all on startup, so the tables can already exist on a database booted
against this code. The exercise suggestions are inserted only into an empty catalogue, so
re-running never duplicates them or brings back one the user deleted.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'b7e3c9a1d5f2'
down_revision: str | None = 'a3d8f2c6b9e4'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

MUSCLE_GROUP = sa.Enum('CHEST', 'BACK', 'SHOULDERS', 'ARMS', 'LEGS', 'CORE', 'FULL_BODY', name='trainrmusclegroup')
EQUIPMENT = sa.Enum('DUMBBELL', 'BARBELL', 'PULL_UP_BAR', 'BODYWEIGHT', 'OTHER', name='trainrequipment')
ACTIVITY_TYPE = sa.Enum('HOME_GYM', 'RUNNING', 'CYCLING', name='trainractivitytype')

# Home-gym suggestions: what can be done with dumbbells, a barbell, a pull-up bar or no kit.
DEFAULT_EXERCISES = [
    ('Dumbbell press', 'CHEST', 'DUMBBELL'),
    ('Incline dumbbell press', 'CHEST', 'DUMBBELL'),
    ('Dumbbell fly', 'CHEST', 'DUMBBELL'),
    ('Barbell bench press', 'CHEST', 'BARBELL'),
    ('Push-up', 'CHEST', 'BODYWEIGHT'),
    ('One-arm dumbbell row', 'BACK', 'DUMBBELL'),
    ('Dumbbell pullover', 'BACK', 'DUMBBELL'),
    ('Barbell row', 'BACK', 'BARBELL'),
    ('Deadlift', 'BACK', 'BARBELL'),
    ('Pull-up', 'BACK', 'PULL_UP_BAR'),
    ('Chin-up', 'BACK', 'PULL_UP_BAR'),
    ('Dumbbell shoulder press', 'SHOULDERS', 'DUMBBELL'),
    ('Arnold press', 'SHOULDERS', 'DUMBBELL'),
    ('Lateral raise', 'SHOULDERS', 'DUMBBELL'),
    ('Front raise', 'SHOULDERS', 'DUMBBELL'),
    ('Rear delt fly', 'SHOULDERS', 'DUMBBELL'),
    ('Overhead press', 'SHOULDERS', 'BARBELL'),
    ('Upright row', 'SHOULDERS', 'BARBELL'),
    ('Dumbbell biceps curl', 'ARMS', 'DUMBBELL'),
    ('Hammer curl', 'ARMS', 'DUMBBELL'),
    ('Barbell curl', 'ARMS', 'BARBELL'),
    ('Overhead triceps extension', 'ARMS', 'DUMBBELL'),
    ('Triceps kickback', 'ARMS', 'DUMBBELL'),
    ('Skull crusher', 'ARMS', 'BARBELL'),
    ('Bench dip', 'ARMS', 'BODYWEIGHT'),
    ('Goblet squat', 'LEGS', 'DUMBBELL'),
    ('Dumbbell lunge', 'LEGS', 'DUMBBELL'),
    ('Bulgarian split squat', 'LEGS', 'DUMBBELL'),
    ('Romanian deadlift', 'LEGS', 'DUMBBELL'),
    ('Step-up', 'LEGS', 'DUMBBELL'),
    ('Barbell back squat', 'LEGS', 'BARBELL'),
    ('Hip thrust', 'LEGS', 'BARBELL'),
    ('Calf raise', 'LEGS', 'DUMBBELL'),
    ('Plank', 'CORE', 'BODYWEIGHT'),
    ('Hanging leg raise', 'CORE', 'PULL_UP_BAR'),
    ('Russian twist', 'CORE', 'DUMBBELL'),
    ('Crunch', 'CORE', 'BODYWEIGHT'),
    ('Dead bug', 'CORE', 'BODYWEIGHT'),
    ('Dumbbell thruster', 'FULL_BODY', 'DUMBBELL'),
    ('Dumbbell swing', 'FULL_BODY', 'DUMBBELL'),
    ('Renegade row', 'FULL_BODY', 'DUMBBELL'),
    ("Farmer's carry", 'FULL_BODY', 'DUMBBELL'),
    ('Burpee', 'FULL_BODY', 'BODYWEIGHT'),
]


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())

    if not inspector.has_table('trainr_exercises'):
        op.create_table(
            'trainr_exercises',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('name', sa.String(120), nullable=False, unique=True),
            sa.Column('muscle_group', MUSCLE_GROUP, nullable=False),
            sa.Column('equipment', EQUIPMENT, nullable=False),
            sa.Column('is_archived', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )

    if not inspector.has_table('trainr_workouts'):
        op.create_table(
            'trainr_workouts',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('activity_type', ACTIVITY_TYPE, nullable=False),
            sa.Column('date', sa.Date(), nullable=False),
            sa.Column('is_completed', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('duration_seconds', sa.Integer(), nullable=True),
            sa.Column('distance_km', sa.Numeric(7, 2), nullable=True),
            sa.Column('max_speed_kmh', sa.Numeric(5, 1), nullable=True),
            sa.Column('notes', sa.Text(), nullable=True),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index('ix_trainr_workouts_date', 'trainr_workouts', ['date'])

    if not inspector.has_table('trainr_workout_entries'):
        op.create_table(
            'trainr_workout_entries',
            sa.Column('id', sa.Integer(), primary_key=True),
            sa.Column('workout_id', sa.Integer(), sa.ForeignKey('trainr_workouts.id', ondelete='CASCADE'), nullable=False),
            sa.Column('exercise_id', sa.Integer(), sa.ForeignKey('trainr_exercises.id'), nullable=False),
            sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
            sa.Column('sets', sa.Integer(), nullable=True),
            sa.Column('reps', sa.Integer(), nullable=True),
            sa.Column('weight_kg', sa.Numeric(6, 2), nullable=True),
            sa.Column('duration_seconds', sa.Integer(), nullable=True),
            sa.Column('notes', sa.String(200), nullable=True),
        )
        op.create_index('ix_trainr_workout_entries_workout_id', 'trainr_workout_entries', ['workout_id'])
        op.create_index('ix_trainr_workout_entries_exercise_id', 'trainr_workout_entries', ['exercise_id'])

    bind = op.get_bind()
    if bind.execute(sa.text('SELECT COUNT(*) FROM trainr_exercises')).scalar_one() == 0:
        exercises = sa.table(
            'trainr_exercises',
            sa.column('name', sa.String),
            sa.column('muscle_group', sa.String),
            sa.column('equipment', sa.String),
            sa.column('is_archived', sa.Boolean),
        )
        op.bulk_insert(
            exercises,
            [{'name': n, 'muscle_group': m, 'equipment': e, 'is_archived': False} for n, m, e in DEFAULT_EXERCISES],
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for table in ('trainr_workout_entries', 'trainr_workouts', 'trainr_exercises'):
        if inspector.has_table(table):
            op.drop_table(table)
