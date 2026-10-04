import io
from datetime import date as date_

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session

from app.db import get_db
from app.repositories import garden_area_repo, garden_care_repo, garden_plant_repo, garden_zone_repo
from app.schemas.gardnr import (
    GardenAreaCreate,
    GardenAreaDetailOut,
    GardenAreaOut,
    GardenAreaReorder,
    GardenAreaUpdate,
    GardenCareLogCreate,
    GardenCareLogOut,
    GardenCareLogUpdate,
    GardenCareScheduleCreate,
    GardenCareScheduleOut,
    GardenCareScheduleUpdate,
    GardenPlantCreate,
    GardenPlantDetailOut,
    GardenPlantListOut,
    GardenPlantMapOut,
    GardenPlantOut,
    GardenPlantUpdate,
    GardenZoneCreate,
    GardenZoneOut,
    GardenZoneUpdate,
)
from app.services import garden_care_service

router = APIRouter(prefix="/api/gardnr", tags=["gardnr"])


def _schedule_out(schedule, logs) -> GardenCareScheduleOut:
    due = garden_care_service.next_due(schedule, logs)
    return GardenCareScheduleOut(
        id=schedule.id,
        plant_id=schedule.plant_id,
        action_type=schedule.action_type,
        custom_label=schedule.custom_label,
        interval_value=schedule.interval_value,
        frequency=schedule.frequency,
        is_active=schedule.is_active,
        start_date=schedule.start_date,
        notes=schedule.notes,
        next_due=due,
        is_overdue=garden_care_service.is_overdue(due),
    )


# -- areas --------------------------------------------------------------------------------


@router.get("/areas", response_model=list[GardenAreaOut])
def list_areas(db: Session = Depends(get_db)):
    plants = garden_plant_repo.list_plants(db)
    plant_ids = [p.id for p in plants]
    logs_by_plant = garden_care_repo.list_logs_for_plants(db, plant_ids)
    schedules_by_plant = garden_care_repo.list_schedules_for_plants(db, plant_ids)

    overdue_by_area: dict[int, int] = {}
    for plant in plants:
        due = garden_care_service.soonest_due_action(schedules_by_plant.get(plant.id, []), logs_by_plant.get(plant.id, []))
        if due is not None and due.is_overdue:
            overdue_by_area[plant.area_id] = overdue_by_area.get(plant.area_id, 0) + 1

    return [
        GardenAreaOut(
            id=a.id, name=a.name, sort_order=a.sort_order, plant_count=count,
            overdue_count=overdue_by_area.get(a.id, 0),
        )
        for a, count in garden_area_repo.list_areas(db)
    ]


@router.post("/areas", response_model=GardenAreaOut)
def create_area(payload: GardenAreaCreate, db: Session = Depends(get_db)):
    area = garden_area_repo.create_area(db, **payload.model_dump())
    db.commit()
    db.refresh(area)
    return GardenAreaOut(id=area.id, name=area.name, sort_order=area.sort_order, plant_count=0)


@router.get("/areas/{area_id}", response_model=GardenAreaDetailOut)
def get_area(area_id: int, db: Session = Depends(get_db)):
    area = garden_area_repo.get_area(db, area_id)
    if area is None:
        raise HTTPException(status_code=404, detail="Area not found")

    zones = garden_zone_repo.list_zones(db, area_id)
    plants = garden_plant_repo.list_plants(db, area_id=area_id)
    plant_ids = [p.id for p in plants]
    logs_by_plant = garden_care_repo.list_logs_for_plants(db, plant_ids)
    schedules_by_plant = garden_care_repo.list_schedules_for_plants(db, plant_ids)

    plant_markers = [
        GardenPlantMapOut(
            id=p.id,
            name=p.name,
            species=p.species,
            type=p.type,
            x=p.x,
            y=p.y,
            marker_shape=p.marker_shape,
            marker_width=p.marker_width,
            marker_height=p.marker_height,
            icon=p.icon,
            status=p.status,
            last_action=garden_care_service.latest_action(logs_by_plant.get(p.id, [])),
            next_action=garden_care_service.soonest_due_action(schedules_by_plant.get(p.id, []), logs_by_plant.get(p.id, [])),
        )
        for p in plants
    ]
    return GardenAreaDetailOut(
        area=GardenAreaOut(id=area.id, name=area.name, sort_order=area.sort_order, plant_count=len(plants)),
        zones=[GardenZoneOut.model_validate(z) for z in zones],
        plants=plant_markers,
    )


@router.put("/areas/reorder", status_code=204)
def reorder_areas(payload: GardenAreaReorder, db: Session = Depends(get_db)):
    garden_area_repo.reorder(db, payload.area_ids)
    db.commit()


@router.put("/areas/{area_id}", response_model=GardenAreaOut)
def update_area(area_id: int, payload: GardenAreaUpdate, db: Session = Depends(get_db)):
    area = garden_area_repo.get_area(db, area_id)
    if area is None:
        raise HTTPException(status_code=404, detail="Area not found")
    garden_area_repo.update_area(db, area, **payload.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(area)
    plant_count = len(garden_plant_repo.list_plants(db, area_id=area_id))
    return GardenAreaOut(id=area.id, name=area.name, sort_order=area.sort_order, plant_count=plant_count)


@router.delete("/areas/{area_id}", status_code=204)
def delete_area(area_id: int, db: Session = Depends(get_db)):
    area = garden_area_repo.get_area(db, area_id)
    if area is None:
        raise HTTPException(status_code=404, detail="Area not found")
    garden_area_repo.delete_area(db, area)
    db.commit()


# -- zones --------------------------------------------------------------------------------


@router.post("/areas/{area_id}/zones", response_model=GardenZoneOut)
def create_zone(area_id: int, payload: GardenZoneCreate, db: Session = Depends(get_db)):
    if garden_area_repo.get_area(db, area_id) is None:
        raise HTTPException(status_code=404, detail="Area not found")
    zone = garden_zone_repo.create_zone(db, area_id=area_id, **payload.model_dump())
    db.commit()
    db.refresh(zone)
    return zone


@router.put("/zones/{zone_id}", response_model=GardenZoneOut)
def update_zone(zone_id: int, payload: GardenZoneUpdate, db: Session = Depends(get_db)):
    zone = garden_zone_repo.get_zone(db, zone_id)
    if zone is None:
        raise HTTPException(status_code=404, detail="Zone not found")
    garden_zone_repo.update_zone(db, zone, **payload.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(zone)
    return zone


@router.delete("/zones/{zone_id}", status_code=204)
def delete_zone(zone_id: int, db: Session = Depends(get_db)):
    zone = garden_zone_repo.get_zone(db, zone_id)
    if zone is None:
        raise HTTPException(status_code=404, detail="Zone not found")
    garden_zone_repo.delete_zone(db, zone)
    db.commit()


# -- plants -------------------------------------------------------------------------------


@router.get("/plants", response_model=list[GardenPlantListOut])
def list_plants(include_archived: bool = False, db: Session = Depends(get_db)):
    plants = garden_plant_repo.list_plants(db, include_archived=include_archived)
    plant_ids = [p.id for p in plants]
    logs_by_plant = garden_care_repo.list_logs_for_plants(db, plant_ids)
    schedules_by_plant = garden_care_repo.list_schedules_for_plants(db, plant_ids)
    areas_by_id = {a.id: a for a, _ in garden_area_repo.list_areas(db)}

    rows = []
    for p in plants:
        actions = garden_care_service.scheduled_actions(schedules_by_plant.get(p.id, []), logs_by_plant.get(p.id, []))
        next_action = actions[0] if actions else None
        rows.append(
            GardenPlantListOut(
                id=p.id,
                area_id=p.area_id,
                area_name=areas_by_id[p.area_id].name if p.area_id in areas_by_id else "",
                name=p.name,
                species=p.species,
                type=p.type,
                status=p.status,
                is_archived=p.is_archived,
                next_action=next_action,
                is_overdue=next_action is not None and garden_care_service.is_overdue(next_action.date),
                scheduled_actions=actions,
            )
        )
    # Soonest/most-overdue action first; plants with no schedule at all sort last.
    rows.sort(key=lambda r: (r.next_action is None, r.next_action.date if r.next_action else date_.max))
    return rows


@router.post("/plants", response_model=GardenPlantOut)
def create_plant(payload: GardenPlantCreate, db: Session = Depends(get_db)):
    if garden_area_repo.get_area(db, payload.area_id) is None:
        raise HTTPException(status_code=404, detail="Area not found")
    plant = garden_plant_repo.create_plant(db, **payload.model_dump())
    db.commit()
    db.refresh(plant)
    return plant


@router.get("/plants/{plant_id}", response_model=GardenPlantDetailOut)
def get_plant(plant_id: int, db: Session = Depends(get_db)):
    plant = garden_plant_repo.get_plant(db, plant_id)
    if plant is None:
        raise HTTPException(status_code=404, detail="Plant not found")
    logs = garden_care_repo.list_logs(db, plant_id)
    schedules = garden_care_repo.list_schedules(db, plant_id)
    return GardenPlantDetailOut(
        plant=GardenPlantOut.model_validate(plant),
        care_logs=[GardenCareLogOut.model_validate(log) for log in logs],
        care_schedules=[_schedule_out(s, logs) for s in schedules],
    )


@router.put("/plants/{plant_id}", response_model=GardenPlantOut)
def update_plant(plant_id: int, payload: GardenPlantUpdate, db: Session = Depends(get_db)):
    plant = garden_plant_repo.get_plant(db, plant_id)
    if plant is None:
        raise HTTPException(status_code=404, detail="Plant not found")
    garden_plant_repo.update_plant(db, plant, **payload.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(plant)
    return plant


@router.delete("/plants/{plant_id}", status_code=204)
def delete_plant(plant_id: int, db: Session = Depends(get_db)):
    plant = garden_plant_repo.get_plant(db, plant_id)
    if plant is None:
        raise HTTPException(status_code=404, detail="Plant not found")
    garden_plant_repo.delete_plant(db, plant)
    db.commit()


# -- care logs ----------------------------------------------------------------------------


@router.post("/plants/{plant_id}/logs", response_model=GardenCareLogOut)
def create_log(plant_id: int, payload: GardenCareLogCreate, db: Session = Depends(get_db)):
    if garden_plant_repo.get_plant(db, plant_id) is None:
        raise HTTPException(status_code=404, detail="Plant not found")
    log = garden_care_repo.create_log(db, plant_id=plant_id, **payload.model_dump())
    db.commit()
    db.refresh(log)
    return log


@router.put("/logs/{log_id}", response_model=GardenCareLogOut)
def update_log(log_id: int, payload: GardenCareLogUpdate, db: Session = Depends(get_db)):
    log = garden_care_repo.get_log(db, log_id)
    if log is None:
        raise HTTPException(status_code=404, detail="Log entry not found")
    garden_care_repo.update_log(db, log, **payload.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(log)
    return log


@router.delete("/logs/{log_id}", status_code=204)
def delete_log(log_id: int, db: Session = Depends(get_db)):
    log = garden_care_repo.get_log(db, log_id)
    if log is None:
        raise HTTPException(status_code=404, detail="Log entry not found")
    garden_care_repo.delete_log(db, log)
    db.commit()


MAX_LOG_PHOTO_UPLOAD_BYTES = 25 * 1024 * 1024
LOG_PHOTO_MAX_DIMENSION = 1600


def _resize_log_photo(raw: bytes) -> bytes:
    """Always re-encoded as a JPEG capped at LOG_PHOTO_MAX_DIMENSION on its longest side, so a
    phone's multi-MB original never lands in portfolio.db as-is -- this table is backed up
    wholesale (docs/adr/0013) and every extra megabyte here is one more in every future backup.
    exif_transpose bakes in a phone photo's rotation, since a raw JPEG's orientation tag is easy
    to lose once it's re-served as plain bytes with no EXIF-aware viewer on the other end.
    """
    from PIL import Image, ImageOps

    with Image.open(io.BytesIO(raw)) as image:
        image = ImageOps.exif_transpose(image)
        image.thumbnail((LOG_PHOTO_MAX_DIMENSION, LOG_PHOTO_MAX_DIMENSION))
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=82)
        return buffer.getvalue()


@router.put("/logs/{log_id}/photo", response_model=GardenCareLogOut)
async def set_log_photo(log_id: int, photo: UploadFile, db: Session = Depends(get_db)):
    """A deliberate attach-a-photo action, separate from the log's own create/update. The upload
    size cap guards against decoding something absurd; the real size control is the resize/
    re-encode below, not this cap."""
    log = garden_care_repo.get_log(db, log_id)
    if log is None:
        raise HTTPException(status_code=404, detail="Log entry not found")
    content = await photo.read()
    if len(content) > MAX_LOG_PHOTO_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Photo too large")
    try:
        resized = _resize_log_photo(content)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Could not read that as an image") from exc
    garden_care_repo.update_log(db, log, photo=resized, photo_content_type="image/jpeg")
    db.commit()
    db.refresh(log)
    return GardenCareLogOut.model_validate(log)


@router.delete("/logs/{log_id}/photo", response_model=GardenCareLogOut)
def delete_log_photo(log_id: int, db: Session = Depends(get_db)):
    log = garden_care_repo.get_log(db, log_id)
    if log is None:
        raise HTTPException(status_code=404, detail="Log entry not found")
    garden_care_repo.update_log(db, log, photo=None, photo_content_type=None)
    db.commit()
    db.refresh(log)
    return GardenCareLogOut.model_validate(log)


@router.get("/logs/{log_id}/photo")
def get_log_photo(log_id: int, db: Session = Depends(get_db)):
    log = garden_care_repo.get_log(db, log_id)
    if log is None or log.photo is None:
        raise HTTPException(status_code=404, detail="No photo")
    return Response(content=log.photo, media_type=log.photo_content_type or "image/jpeg")


# -- care schedules -------------------------------------------------------------------------


@router.post("/plants/{plant_id}/schedules", response_model=GardenCareScheduleOut)
def create_schedule(plant_id: int, payload: GardenCareScheduleCreate, db: Session = Depends(get_db)):
    if garden_plant_repo.get_plant(db, plant_id) is None:
        raise HTTPException(status_code=404, detail="Plant not found")
    schedule = garden_care_repo.create_schedule(db, plant_id=plant_id, **payload.model_dump())
    db.commit()
    db.refresh(schedule)
    return _schedule_out(schedule, garden_care_repo.list_logs(db, schedule.plant_id))


@router.put("/schedules/{schedule_id}", response_model=GardenCareScheduleOut)
def update_schedule(schedule_id: int, payload: GardenCareScheduleUpdate, db: Session = Depends(get_db)):
    schedule = garden_care_repo.get_schedule(db, schedule_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    garden_care_repo.update_schedule(db, schedule, **payload.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(schedule)
    return _schedule_out(schedule, garden_care_repo.list_logs(db, schedule.plant_id))


@router.delete("/schedules/{schedule_id}", status_code=204)
def delete_schedule(schedule_id: int, db: Session = Depends(get_db)):
    schedule = garden_care_repo.get_schedule(db, schedule_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail="Schedule not found")
    garden_care_repo.delete_schedule(db, schedule)
    db.commit()
