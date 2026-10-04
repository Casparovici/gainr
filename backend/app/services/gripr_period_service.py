"""The one shared "what period does this date fall in" primitive, used by both budgeting and
overview reporting so gripr's period boundary — configurable, default the calendar month — is
computed in exactly one place. See docs/adr/0004-gripr-period-boundary.md.
"""

from datetime import date as date_, timedelta

from dateutil.relativedelta import relativedelta



def period_bounds(reference_date: date_, start_day: int) -> tuple[date_, date_]:
    """The period `reference_date` falls in, given a period that always starts on
    `start_day` of some month and runs to the day before the next occurrence of `start_day`.

    At `start_day == 1` this is exactly the calendar month `reference_date` falls in — the
    special case every existing budget/overview call site relied on before this was
    configurable.
    """
    if reference_date.day >= start_day:
        start = date_(reference_date.year, reference_date.month, start_day)
    else:
        prev = reference_date - relativedelta(months=1)
        start = date_(prev.year, prev.month, start_day)
    end = start + relativedelta(months=1) - timedelta(days=1)
    return start, end

