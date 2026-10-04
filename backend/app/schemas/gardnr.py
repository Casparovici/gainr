from datetime import date as date_
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.garden_care import GardenActionType, GardenScheduleFrequency
from app.models.garden_plant import GardenPlantIcon, GardenPlantStatus, GardenPlantType
from app.models.garden_zone import GardenZoneShape

# -- areas --------------------------------------------------------------------------------


class GardenAreaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    sort_order: int
    plant_count: int = 0
    # Plants in this area with at least one overdue scheduled action — the signal that decides
    # which garden to walk into first, so the tile grid can show it without opening each area.
    overdue_count: int = 0


class GardenAreaCreate(BaseModel):
    name: str


class GardenAreaUpdate(BaseModel):
    name: str | None = None


class GardenAreaReorder(BaseModel):
    area_ids: list[int]


# -- zones --------------------------------------------------------------------------------


class GardenZoneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    area_id: int
    name: str
    shape: GardenZoneShape
    x: Decimal
    y: Decimal
    width: Decimal
    height: Decimal
    color: str
    sort_order: int


class GardenZoneCreate(BaseModel):
    name: str
    shape: GardenZoneShape
    x: Decimal
    y: Decimal
    width: Decimal
    height: Decimal
    color: str


class GardenZoneUpdate(BaseModel):
    name: str | None = None
    x: Decimal | None = None
    y: Decimal | None = None
    width: Decimal | None = None
    height: Decimal | None = None
    color: str | None = None


# -- care logs ----------------------------------------------------------------------------


class GardenCareLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plant_id: int
    action_type: GardenActionType
    custom_label: str | None
    performed_on: date_
    notes: str | None
    # The photo itself is never on this wire -- GET /logs/{id}/photo serves the bytes directly,
    # so a log list stays lean regardless of how many entries carry a photo.
    has_photo: bool = False


class GardenCareLogCreate(BaseModel):
    action_type: GardenActionType
    custom_label: str | None = None
    performed_on: date_
    notes: str | None = None


class GardenCareLogUpdate(BaseModel):
    action_type: GardenActionType | None = None
    custom_label: str | None = None
    performed_on: date_ | None = None
    notes: str | None = None


# -- care schedules -------------------------------------------------------------------------
# `next_due`/`is_overdue` are computed by garden_care_service, never stored -- see
# GardenCareSchedule's docstring for why.


class GardenCareScheduleOut(BaseModel):
    id: int
    plant_id: int
    action_type: GardenActionType
    custom_label: str | None
    interval_value: int
    frequency: GardenScheduleFrequency
    is_active: bool
    start_date: date_ | None
    notes: str | None
    next_due: date_
    is_overdue: bool


class GardenCareScheduleCreate(BaseModel):
    action_type: GardenActionType
    custom_label: str | None = None
    interval_value: int = Field(default=1, ge=1)
    frequency: GardenScheduleFrequency
    start_date: date_ | None = None
    notes: str | None = None


class GardenCareScheduleUpdate(BaseModel):
    action_type: GardenActionType | None = None
    custom_label: str | None = None
    interval_value: int | None = Field(default=None, ge=1)
    frequency: GardenScheduleFrequency | None = None
    is_active: bool | None = None
    start_date: date_ | None = None
    notes: str | None = None


# -- plants -------------------------------------------------------------------------------


class GardenActionSummary(BaseModel):
    # Which schedule produced this occurrence; None for a summary of a past log (`last_action`).
    schedule_id: int | None = None
    action_type: GardenActionType
    custom_label: str | None
    date: date_
    # Carried on the wire rather than derived per-surface: the map used to recompute this from
    # `date` in the browser, which disagreed with the backend's own answer around midnight and
    # across timezones. One definition, in garden_care_service.
    is_overdue: bool = False


class GardenPlantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    area_id: int
    name: str
    species: str | None
    type: GardenPlantType
    planted_date: date_ | None
    notes: str | None
    x: Decimal | None
    y: Decimal | None
    marker_shape: GardenZoneShape
    marker_width: Decimal
    marker_height: Decimal
    icon: GardenPlantIcon | None
    status: GardenPlantStatus
    is_archived: bool


class GardenPlantCreate(BaseModel):
    area_id: int
    name: str
    species: str | None = None
    type: GardenPlantType
    planted_date: date_ | None = None
    notes: str | None = None
    x: Decimal | None = None
    y: Decimal | None = None
    marker_shape: GardenZoneShape = GardenZoneShape.CIRCLE
    marker_width: Decimal = Decimal("6.00")
    marker_height: Decimal = Decimal("6.00")
    icon: GardenPlantIcon | None = None
    status: GardenPlantStatus = GardenPlantStatus.THRIVING


class GardenPlantUpdate(BaseModel):
    name: str | None = None
    species: str | None = None
    type: GardenPlantType | None = None
    planted_date: date_ | None = None
    notes: str | None = None
    x: Decimal | None = None
    y: Decimal | None = None
    marker_shape: GardenZoneShape | None = None
    marker_width: Decimal | None = None
    marker_height: Decimal | None = None
    icon: GardenPlantIcon | None = None
    status: GardenPlantStatus | None = None
    is_archived: bool | None = None


class GardenPlantMapOut(BaseModel):
    """One marker on an area's map -- just enough for the canvas and its hover card."""

    id: int
    name: str
    species: str | None
    type: GardenPlantType
    x: Decimal | None
    y: Decimal | None
    marker_shape: GardenZoneShape
    marker_width: Decimal
    marker_height: Decimal
    icon: GardenPlantIcon | None
    status: GardenPlantStatus
    last_action: GardenActionSummary | None
    next_action: GardenActionSummary | None


class GardenAreaDetailOut(BaseModel):
    area: GardenAreaOut
    zones: list[GardenZoneOut]
    plants: list[GardenPlantMapOut]


class GardenPlantListOut(BaseModel):
    """One row on the flat Plants catalog page, sorted soonest/most-overdue action first."""

    id: int
    area_id: int
    area_name: str
    name: str
    species: str | None
    type: GardenPlantType
    status: GardenPlantStatus
    is_archived: bool
    next_action: GardenActionSummary | None
    is_overdue: bool
    # Every active schedule's next occurrence, soonest first; `next_action` is its first entry.
    scheduled_actions: list[GardenActionSummary]


class GardenPlantDetailOut(BaseModel):
    plant: GardenPlantOut
    care_logs: list[GardenCareLogOut]
    care_schedules: list[GardenCareScheduleOut]
