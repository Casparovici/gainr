"""trainr: importing rides and runs from a Strava account export (activities.csv).

The file is what Strava's "Download or delete your account" archive contains, not a live API, so
there's no provider adapter, key or network call here: the script hands in the file's text and
this module parses it and books the activities (docs/adr/0037, addendum).

The export's header repeats some names: the first "Distance"/"Elapsed Time" are the summary in
display units (km), a later block repeats them in raw units (metres, seconds, m/s) next to
"Moving Time" and "Max Speed". The raw block is preferred; a single "Distance" (older exports)
is read as km. Headers, type names and dates follow the account's language; English and Dutch are
both read."""

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date as date_, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models.trainr_workout import TrainrActivityType
from app.repositories import trainr_workout_repo

# Strava stamps activities in UTC; the day a ride belongs to is the one it was ridden on here.
LOCAL_TZ = ZoneInfo("Europe/Amsterdam")
SOURCE_PREFIX = "strava:"

# Activity types, normalised (lowercase, no spaces/hyphens/underscores). Anything else -- walks,
# swims, weight training -- is skipped and counted, so an unexpected type shows up in the report.
TYPE_MAP: dict[str, TrainrActivityType] = {
    **{t: TrainrActivityType.CYCLING for t in (
        "ride", "virtualride", "ebikeride", "gravelride", "mountainbikeride", "emountainbikeride",
        "velomobile", "handcycle", "fietsrit", "virtuelefietsrit", "ebikerit", "elektrischefietsrit",
        "gravelrit", "mountainbikerit", "elektrischemountainbikerit",
    )},
    **{t: TrainrActivityType.RUNNING for t in (
        "run", "trailrun", "virtualrun", "hardloopsessie", "hardlopen", "trailrunsessie",
        "virtuelehardloopsessie", "virtueelhardlopen",
    )},
}

# Each column the importer reads, under its English and its Dutch header.
COLUMNS: dict[str, tuple[str, ...]] = {
    "id": ("Activity ID", "Activiteits-ID"),
    "date": ("Activity Date", "Datum van activiteit"),
    "name": ("Activity Name", "Naam activiteit"),
    "type": ("Activity Type", "Activiteitstype"),
    "distance": ("Distance", "Afstand"),
    "moving": ("Moving Time", "Beweegtijd"),
    "elapsed": ("Elapsed Time", "Verstreken tijd"),
    "max_speed": ("Max Speed", "Max. snelheid"),
}

_MONTHS = {
    # English and Dutch abbreviations, as the export writes them depending on the account's language.
    "jan": 1, "feb": 2, "mar": 3, "mrt": 3, "apr": 4, "may": 5, "mei": 5, "jun": 6, "jul": 7,
    "aug": 8, "sep": 9, "oct": 10, "okt": 10, "nov": 11, "dec": 12,
}
# "Mar 14, 2023, 6:02:11 PM" (English) and "14 mrt. 2023, 18:02:11" (Dutch).
_EN_DATE = re.compile(r"^([A-Za-z]{3})\w*\.? (\d{1,2}), (\d{4}),? (\d{1,2}):(\d{2}):(\d{2})\s*([AP]M)?$", re.IGNORECASE)
_NL_DATE = re.compile(r"^(\d{1,2}) ([A-Za-z]{3})\w*\.? (\d{4}),? (\d{1,2}):(\d{2}):(\d{2})$")


class StravaExportError(ValueError):
    """The file isn't a Strava activities.csv the importer can read."""


@dataclass
class StravaActivity:
    activity_id: str
    started_at: datetime  # UTC
    name: str
    activity_type: str
    distance_km: Decimal | None
    duration_seconds: int | None
    max_speed_kmh: Decimal | None

    @property
    def local_date(self) -> date_:
        return self.started_at.astimezone(LOCAL_TZ).date()


@dataclass
class StravaImportResult:
    imported: int = 0
    already_imported: int = 0
    skipped_types: dict[str, int] = field(default_factory=dict)
    by_activity: dict[TrainrActivityType, int] = field(default_factory=dict)


def normalise_type(value: str) -> str:
    return re.sub(r"[\s\-_]", "", value).lower()


def parse_number(value: str | None) -> Decimal | None:
    """"12345.6", "1,234.5" or "12,5" -> Decimal; empty or unreadable -> None."""
    if value is None:
        return None
    text = value.strip().replace(" ", "").replace(" ", "")
    if not text:
        return None
    if "," in text and "." in text:
        # Whichever comes last is the decimal separator; the other groups thousands.
        text = text.replace(",", "") if text.rfind(".") > text.rfind(",") else text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def parse_date(value: str) -> datetime:
    text = value.strip()
    try:
        parsed = datetime.fromisoformat(text)
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
    except ValueError:
        pass
    if m := _EN_DATE.match(text):
        mon, day, year, hour, minute, second, ampm = m.groups()
        hour_i = int(hour)
        if ampm:
            hour_i = hour_i % 12 + (12 if ampm.upper() == "PM" else 0)
    elif m := _NL_DATE.match(text):
        day, mon, year, hour, minute, second = m.groups()
        hour_i = int(hour)
    else:
        raise StravaExportError(f"Unreadable activity date: {value!r}")
    month = _MONTHS.get(mon[:3].lower())
    if month is None:
        raise StravaExportError(f"Unreadable month in activity date: {value!r}")
    return datetime(int(year), month, int(day), hour_i, int(minute), int(second), tzinfo=timezone.utc)


def parse_activities_csv(text: str) -> list[StravaActivity]:
    rows = list(csv.reader(io.StringIO(text.lstrip("﻿"))))
    if not rows:
        raise StravaExportError("The file is empty")
    header = [h.strip() for h in rows[0]]

    def positions(key: str) -> list[int]:
        return [i for i, h in enumerate(header) if h in COLUMNS[key]]

    for required in ("id", "date", "type"):
        if not positions(required):
            raise StravaExportError(f"No {COLUMNS[required][0]!r} column -- is this Strava's activities.csv?")
    id_col, date_col, type_col = positions("id")[0], positions("date")[0], positions("type")[0]
    name_col = (positions("name") or [None])[0]
    distances = positions("distance")
    moving = positions("moving")
    elapsed = positions("elapsed")
    max_speed = positions("max_speed")

    def cell(row: list[str], col: int | None) -> str | None:
        return row[col] if col is not None and col < len(row) else None

    activities = []
    for row in rows[1:]:
        if not row or not (cell(row, id_col) or "").strip():
            continue
        if len(distances) >= 2:
            metres = parse_number(cell(row, distances[-1]))
            distance_km = metres / 1000 if metres is not None else None
        else:
            distance_km = parse_number(cell(row, distances[0])) if distances else None
        seconds = parse_number(cell(row, moving[-1])) if moving else None
        if not seconds and elapsed:
            seconds = parse_number(cell(row, elapsed[-1]))
        speed_ms = parse_number(cell(row, max_speed[-1])) if max_speed else None
        activities.append(
            StravaActivity(
                activity_id=cell(row, id_col).strip(),
                started_at=parse_date(cell(row, date_col) or ""),
                name=(cell(row, name_col) or "").strip(),
                activity_type=(cell(row, type_col) or "").strip(),
                distance_km=distance_km.quantize(Decimal("0.01"), ROUND_HALF_UP) if distance_km else None,
                duration_seconds=int(seconds) if seconds else None,
                max_speed_kmh=(speed_ms * Decimal("3.6")).quantize(Decimal("0.1"), ROUND_HALF_UP) if speed_ms else None,
            )
        )
    return activities


def import_activities(db: Session, activities: list[StravaActivity]) -> StravaImportResult:
    """Books every ride and run as a done workout, skipping what an earlier run already imported
    (matched on source_ref). Doesn't commit -- the caller decides, so a dry run can roll back."""
    result = StravaImportResult()
    wanted = [a for a in activities if normalise_type(a.activity_type) in TYPE_MAP]
    for a in activities:
        if normalise_type(a.activity_type) not in TYPE_MAP:
            result.skipped_types[a.activity_type] = result.skipped_types.get(a.activity_type, 0) + 1
    existing = trainr_workout_repo.existing_source_refs(db, {SOURCE_PREFIX + a.activity_id for a in wanted})
    for a in wanted:
        ref = SOURCE_PREFIX + a.activity_id
        if ref in existing:
            result.already_imported += 1
            continue
        activity_type = TYPE_MAP[normalise_type(a.activity_type)]
        trainr_workout_repo.create_workout(
            db,
            entries=[],
            activity_type=activity_type,
            date=a.local_date,
            is_completed=True,
            distance_km=a.distance_km,
            duration_seconds=a.duration_seconds,
            max_speed_kmh=a.max_speed_kmh,
            notes=a.name or None,
            source_ref=ref,
        )
        existing.add(ref)  # the same activity twice in one file books once
        result.imported += 1
        result.by_activity[activity_type] = result.by_activity.get(activity_type, 0) + 1
    return result
