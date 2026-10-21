"""trainr: an exercise can link a how-to demo

Revision ID: f2b8d4a6c1e7
Revises: e5a1c7d9b3f4
Create Date: 2026-10-18 12:00:00.000000

A nullable `demo_id` on trainr_exercises: the id of an exercise in the vendored free-exercise-db
catalogue (docs/adr/0040-trainr-exercise-demos.md). The column is guarded because create_all never
adds a column to an existing table. The seeded suggestions are then linked by name -- their seed
name or the catalogue's own name for the demo, ignoring case and punctuation -- but only where
nothing is linked yet, so a demo the user picked is never overwritten. Burpee has no demo in the
catalogue and stays unlinked.
"""
import re
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'f2b8d4a6c1e7'
down_revision: str | None = 'e5a1c7d9b3f4'
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

# The ADR 0037 seed (and the catalogue's own name for each demo) -> the demo's id.
SEED_DEMOS = {
    'Dumbbell press': 'Dumbbell_Bench_Press',
    'Incline dumbbell press': 'Incline_Dumbbell_Press',
    'Dumbbell fly': 'Dumbbell_Flyes',
    'Barbell bench press': 'Barbell_Bench_Press_-_Medium_Grip',
    'Push-up': 'Pushups',
    'One-arm dumbbell row': 'One-Arm_Dumbbell_Row',
    'Dumbbell pullover': 'Straight-Arm_Dumbbell_Pullover',
    'Barbell row': 'Bent_Over_Barbell_Row',
    'Deadlift': 'Barbell_Deadlift',
    'Pull-up': 'Pullups',
    'Chin-up': 'Chin-Up',
    'Dumbbell shoulder press': 'Dumbbell_Shoulder_Press',
    'Arnold press': 'Arnold_Dumbbell_Press',
    'Lateral raise': 'Side_Lateral_Raise',
    'Front raise': 'Front_Dumbbell_Raise',
    'Rear delt fly': 'Seated_Bent-Over_Rear_Delt_Raise',
    'Overhead press': 'Standing_Military_Press',
    'Upright row': 'Upright_Barbell_Row',
    'Dumbbell biceps curl': 'Dumbbell_Bicep_Curl',
    'Hammer curl': 'Hammer_Curls',
    'Barbell curl': 'Barbell_Curl',
    'Overhead triceps extension': 'Seated_Triceps_Press',
    'Triceps kickback': 'Tricep_Dumbbell_Kickback',
    'Skull crusher': 'EZ-Bar_Skullcrusher',
    'Bench dip': 'Bench_Dips',
    'Goblet squat': 'Goblet_Squat',
    'Dumbbell lunge': 'Dumbbell_Lunges',
    'Bulgarian split squat': 'Split_Squat_with_Dumbbells',
    'Romanian deadlift': 'Stiff-Legged_Dumbbell_Deadlift',
    'Step-up': 'Dumbbell_Step_Ups',
    'Barbell back squat': 'Barbell_Squat',
    'Hip thrust': 'Barbell_Hip_Thrust',
    'Calf raise': 'Standing_Dumbbell_Calf_Raise',
    'Plank': 'Plank',
    'Hanging leg raise': 'Hanging_Leg_Raise',
    'Russian twist': 'Russian_Twist',
    'Crunch': 'Crunches',
    'Dead bug': 'Dead_Bug',
    'Dumbbell thruster': 'Kettlebell_Thruster',
    'Dumbbell swing': 'Vertical_Swing',
    'Renegade row': 'Alternating_Renegade_Row',
    "Farmer's carry": 'Farmers_Walk',
}


def _normalise(text: str) -> str:
    return re.sub(r'[^a-z0-9]', '', text.lower())


def _by_name() -> dict[str, str]:
    # A demo id spelled out ("Dumbbell_Bicep_Curl" -> "Dumbbell Bicep Curl") is close to the
    # catalogue's name for it, so a renamed suggestion that took that name still matches.
    names = {}
    for seed, demo_id in SEED_DEMOS.items():
        names[_normalise(seed)] = demo_id
        names.setdefault(_normalise(demo_id), demo_id)
    return names


def upgrade() -> None:
    bind = op.get_bind()
    existing = {c['name'] for c in sa.inspect(bind).get_columns('trainr_exercises')}
    if 'demo_id' not in existing:
        with op.batch_alter_table('trainr_exercises') as batch:
            batch.add_column(sa.Column('demo_id', sa.String(120), nullable=True))

    by_name = _by_name()
    rows = bind.execute(sa.text('SELECT id, name FROM trainr_exercises WHERE demo_id IS NULL')).all()
    for exercise_id, name in rows:
        demo_id = by_name.get(_normalise(name))
        if demo_id:
            bind.execute(
                sa.text('UPDATE trainr_exercises SET demo_id = :demo_id WHERE id = :id'),
                {'demo_id': demo_id, 'id': exercise_id},
            )


def downgrade() -> None:
    existing = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('trainr_exercises')}
    if 'demo_id' in existing:
        with op.batch_alter_table('trainr_exercises') as batch:
            batch.drop_column('demo_id')
