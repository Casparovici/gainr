from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.models.trainr_workout import TrainrActivityType, TrainrWorkout
from app.services import trainr_strava_import as strava

# The real export's layout: summary Elapsed Time/Distance (km) first, then a raw block repeating
# them in seconds/metres next to Moving Time and Max Speed (m/s).
HEADER = (
    "Activity ID,Activity Date,Activity Name,Activity Type,Activity Description,Elapsed Time,Distance,"
    "Max Heart Rate,Relative Effort,Commute,Activity Private Note,Activity Gear,Filename,Athlete Weight,"
    "Bike Weight,Elapsed Time,Moving Time,Distance,Max Speed,Average Speed,Elevation Gain"
)


def row(activity_id, when, name, type_, elapsed, km, moving, metres, max_ms):
    return f'{activity_id},"{when}",{name},{type_},,{elapsed},{km},,,false,,,,,,{elapsed},{moving},{metres},{max_ms},,120'


EXPORT = "\n".join(
    [
        HEADER,
        row(111, "Mar 14, 2026, 6:02:11 PM", "Avondrit", "Ride", 5700, "42.35", 5400, "42351.2", "13.5"),
        row(222, "Mar 15, 2026, 11:30:00 PM", "Late run", "Run", 1900, "5.01", 1800, "5012.0", "4.4"),
        row(333, "Mar 16, 2026, 9:00:00 AM", "Wandeling", "Walk", 3600, "4.2", 3500, "4200.0", "1.7"),
        row(444, "Mar 17, 2026, 7:15:00 AM", "Zwift", "Virtual Ride", 3600, "30.0", 3600, "30000.0", ""),
    ]
)


def test_parse_reads_the_raw_block_and_converts_units():
    ride, run, walk, zwift = strava.parse_activities_csv(EXPORT)

    assert ride.activity_id == "111"
    assert ride.started_at == datetime(2026, 3, 14, 18, 2, 11, tzinfo=timezone.utc)
    assert ride.distance_km == Decimal("42.35")  # 42351.2 m
    assert ride.duration_seconds == 5400  # moving time, not elapsed
    assert ride.max_speed_kmh == Decimal("48.6")  # 13.5 m/s
    assert zwift.max_speed_kmh is None


def test_an_activity_late_in_the_evening_utc_lands_on_the_local_next_day():
    run = strava.parse_activities_csv(EXPORT)[1]
    assert run.local_date == date(2026, 3, 16)  # 23:30 UTC is 00:30 in Amsterdam


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Mar 14, 2026, 6:02:11 PM", datetime(2026, 3, 14, 18, 2, 11, tzinfo=timezone.utc)),
        ("Jan 1, 2026, 12:05:00 AM", datetime(2026, 1, 1, 0, 5, 0, tzinfo=timezone.utc)),
        ("14 mrt. 2026, 18:02:11", datetime(2026, 3, 14, 18, 2, 11, tzinfo=timezone.utc)),
        ("3 okt 2026, 07:00:00", datetime(2026, 10, 3, 7, 0, 0, tzinfo=timezone.utc)),
        ("2026-03-14 18:02:11", datetime(2026, 3, 14, 18, 2, 11, tzinfo=timezone.utc)),
    ],
)
def test_parse_date_reads_english_dutch_and_iso(text, expected):
    assert strava.parse_date(text) == expected


def test_parse_date_rejects_garbage():
    with pytest.raises(strava.StravaExportError):
        strava.parse_date("yesterday")


@pytest.mark.parametrize("text, expected", [("12345.6", "12345.6"), ("1,234.5", "1234.5"), ("1.234,5", "1234.5"), ("12,5", "12.5"), ("", None), ("n/a", None)])
def test_parse_number(text, expected):
    assert strava.parse_number(text) == (Decimal(expected) if expected else None)


def test_a_dutch_export_reads_the_same():
    header = (
        "Activiteits-ID,Datum van activiteit,Naam activiteit,Activiteitstype,Beschrijving van activiteit,Verstreken tijd,"
        "Afstand,Max. hartslag,Vergelijkbare poging,Woon-werkverkeer,Privénotitie activiteit,Uitrusting voor activiteit,"
        "Bestandsnaam,Gewicht sporter,Gewicht fiets,Verstreken tijd,Beweegtijd,Afstand,Max. snelheid,Gemiddelde snelheid"
    )
    text = "\n".join(
        [
            header,
            '1,"5 okt 2026, 07:00:47",Ochtendrit,Fietsrit,,4578,"23,61",,,false,,,,,,4578.0,3679.0,23613.5,12.94,6.418',
            '2,"12 okt 2026, 10:34:56",Rondje,Hardloopsessie,,1894,"5,00",,,false,,,,,,1894.0,1835.0,5007.3,4.92,2.729',
            '3,"1 okt 2026, 19:00:00",Zwift,Virtuele fietsrit,,3600,"30,00",,,false,,,,,,3600.0,3600.0,30000.0,,',
        ]
    )

    ride, run, zwift = strava.parse_activities_csv(text)

    assert (ride.distance_km, ride.duration_seconds, ride.max_speed_kmh) == (Decimal("23.61"), 3679, Decimal("46.6"))
    assert ride.local_date == date(2026, 10, 5)
    assert run.distance_km == Decimal("5.01")
    assert [strava.TYPE_MAP[strava.normalise_type(a.activity_type)] for a in (ride, run, zwift)] == [
        TrainrActivityType.CYCLING,
        TrainrActivityType.RUNNING,
        TrainrActivityType.CYCLING,
    ]


def test_a_single_distance_column_is_read_as_km():
    text = 'Activity ID,Activity Date,Activity Type,Distance,Elapsed Time\n9,"Mar 14, 2026, 6:00:00 PM",Run,"10.5",3000'
    (run,) = strava.parse_activities_csv(text)
    assert run.distance_km == Decimal("10.50")
    assert run.duration_seconds == 3000


def test_a_file_that_isnt_the_export_is_refused():
    with pytest.raises(strava.StravaExportError):
        strava.parse_activities_csv("Date,Amount\n2026-01-01,5")


def test_import_books_rides_and_runs_once_and_reports_skipped_types(db_session):
    activities = strava.parse_activities_csv(EXPORT)

    first = strava.import_activities(db_session, activities)
    db_session.commit()
    again = strava.import_activities(db_session, activities)

    assert first.imported == 3
    assert first.by_activity == {TrainrActivityType.CYCLING: 2, TrainrActivityType.RUNNING: 1}
    assert first.skipped_types == {"Walk": 1}
    assert again.imported == 0 and again.already_imported == 3

    ride = db_session.query(TrainrWorkout).filter_by(source_ref="strava:111").one()
    assert ride.activity_type == TrainrActivityType.CYCLING
    assert ride.is_completed is True
    assert ride.date == date(2026, 3, 14)
    assert ride.notes == "Avondrit"
    assert ride.distance_km == Decimal("42.35")


def test_the_same_activity_twice_in_one_file_books_once(db_session):
    activities = strava.parse_activities_csv(EXPORT)[:1] * 2
    assert strava.import_activities(db_session, activities).imported == 1
