"""gardnr's contribution to taskr's agenda: every active care schedule's next occurrence. The
due dates are the ones gardnr already computes on read (garden_care_service.next_due); nothing is
stored here."""

from datetime import date as date_

from sqlalchemy.orm import Session

from app.models.garden_care import GardenActionType
from app.repositories import garden_care_repo, garden_plant_repo
from app.schemas.taskr import AgendaItemOut, AgendaSource
from app.services import garden_care_service

_LABEL = {
    GardenActionType.WATER: "Water",
    GardenActionType.PRUNE: "Prune",
    GardenActionType.TRIM: "Trim",
    GardenActionType.FERTILIZE: "Fertilize",
    GardenActionType.HARVEST: "Harvest",
    GardenActionType.PEST_CONTROL: "Pest control for",
    GardenActionType.OTHER: "Care for",
}


def agenda_items(db: Session, date_to: date_, today: date_) -> list[AgendaItemOut]:
    """Care actions due on or before `date_to`, with anything already due included (a schedule
    that is overdue stays on the agenda until it's logged)."""
    plants = garden_plant_repo.list_plants(db)
    plant_ids = [p.id for p in plants]
    logs_by_plant = garden_care_repo.list_logs_for_plants(db, plant_ids)
    schedules_by_plant = garden_care_repo.list_schedules_for_plants(db, plant_ids)

    items = []
    for plant in plants:
        actions = garden_care_service.scheduled_actions(
            schedules_by_plant.get(plant.id, []), logs_by_plant.get(plant.id, []), today
        )
        for action in actions:
            if action.date > date_to:
                continue
            if action.action_type == GardenActionType.OTHER and action.custom_label:
                title = f"{action.custom_label}: {plant.name}"
            else:
                title = f"{_LABEL[action.action_type]} {plant.name}"
            items.append(
                AgendaItemOut(
                    key=f"gardnr:schedule:{action.schedule_id}",
                    source=AgendaSource.GARDNR,
                    title=title,
                    due_date=action.date,
                    is_overdue=action.date < today,
                    link="/gardnr/vandaag",
                )
            )
    return items
