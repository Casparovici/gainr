"""trainr's contribution to taskr's agenda: planned workouts that aren't ticked off yet. A planned
workout is the same row as a done one (docs/adr/0037), so completing it in trainr removes it from
the agenda with no sync step."""

from datetime import date as date_, timedelta

from sqlalchemy.orm import Session

from app.models.trainr_workout import TrainrActivityType
from app.repositories import trainr_workout_repo
from app.schemas.taskr import AgendaItemOut, AgendaSource

_LABEL = {
    TrainrActivityType.HOME_GYM: "Home gym",
    TrainrActivityType.RUNNING: "Run",
    TrainrActivityType.CYCLING: "Ride",
    TrainrActivityType.FOOTBALL: "Football",
    TrainrActivityType.PADEL: "Padel",
}

# How far back an unticked planned workout still counts as overdue. A session planned months ago
# and never logged is history nobody will tick off, and would otherwise sit on the agenda forever.
OVERDUE_LOOKBACK_DAYS = 14


def agenda_items(db: Session, date_to: date_, today: date_) -> list[AgendaItemOut]:
    workouts = trainr_workout_repo.list_range(
        db, today - timedelta(days=OVERDUE_LOOKBACK_DAYS), date_to, completed=False
    )
    return [
        AgendaItemOut(
            key=f"trainr:workout:{w.id}",
            source=AgendaSource.TRAINR,
            title=_LABEL[w.activity_type],
            detail=_detail(w),
            due_date=w.date,
            is_overdue=w.date < today,
            link="/trainr",
        )
        for w in workouts
    ]


def _detail(workout) -> str | None:
    if workout.distance_km is not None:
        return f"{workout.distance_km.normalize():f} km"
    if workout.entries:
        count = len(workout.entries)
        return f"{count} exercise{'s' if count != 1 else ''}"
    return None
