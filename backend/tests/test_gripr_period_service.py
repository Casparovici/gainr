from datetime import date, timedelta

from app.services.gripr_period_service import period_bounds


def calendar_month_bounds(d: date) -> tuple[date, date]:
    """The old `month_bounds` this replaces — kept here only as the regression baseline."""
    import calendar

    start = date(d.year, d.month, 1)
    end = date(d.year, d.month, calendar.monthrange(d.year, d.month)[1])
    return start, end


def test_start_day_one_matches_plain_calendar_month_bounds():
    for d in [date(2026, 1, 1), date(2026, 1, 31), date(2026, 2, 15), date(2024, 2, 29)]:
        assert period_bounds(d, 1) == calendar_month_bounds(d)


def test_reference_date_before_the_start_day_falls_in_the_previous_periods_start():
    # The 13th, with periods starting the 25th, is still inside the period that began Aug 25.
    assert period_bounds(date(2026, 9, 13), 25) == (date(2026, 8, 25), date(2026, 9, 24))


def test_reference_date_on_the_start_day_begins_a_new_period():
    assert period_bounds(date(2026, 9, 25), 25) == (date(2026, 9, 25), date(2026, 10, 24))


def test_reference_date_after_the_start_day_falls_in_the_current_periods_start():
    assert period_bounds(date(2026, 9, 30), 25) == (date(2026, 9, 25), date(2026, 10, 24))


def test_period_end_is_always_the_day_before_the_next_periods_start():
    start, end = period_bounds(date(2026, 9, 13), 25)
    next_start, _ = period_bounds(end + timedelta(days=1), 25)
    assert next_start == end + timedelta(days=1)
    assert next_start != start


def test_period_bounds_works_across_a_year_boundary():
    assert period_bounds(date(2027, 1, 5), 25) == (date(2026, 12, 25), date(2027, 1, 24))
