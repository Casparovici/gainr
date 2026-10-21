"""briefr: the Sunday gym plan for the coming week (docs/adr/0046). trainr's rules make the plan
and put the sessions in its planner (trainr_plan_service); this writes the Dutch report that says
what the last three weeks looked like and why the week looks the way it does. Written by the
server: the workout history never leaves it."""

from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from app.models.briefr_report import BriefrAttention, BriefrVerdict
from app.models.trainr_exercise import TrainrMuscleGroup
from app.models.trainr_workout import TrainrActivityType
from app.schemas.briefr import ReportFileItem
from app.services import briefr_report_service, trainr_plan_service
from app.services.briefr_report_service import ParsedReport
from app.services.trainr_plan import PLANNED_SETS, Performance, Target, WeekPlan

AGENT = "trainr-weekplan"
DAYS = ["maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag", "zondag"]
MONTHS = ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"]
GROUPS = {
    TrainrMuscleGroup.CHEST: "borst", TrainrMuscleGroup.BACK: "rug", TrainrMuscleGroup.SHOULDERS: "schouders",
    TrainrMuscleGroup.ARMS: "armen", TrainrMuscleGroup.LEGS: "benen", TrainrMuscleGroup.CORE: "core",
    TrainrMuscleGroup.FULL_BODY: "full body",
}
SPORTS = {
    TrainrActivityType.RUNNING: "hardlopen", TrainrActivityType.CYCLING: "fietsen",
    TrainrActivityType.FOOTBALL: "voetbal", TrainrActivityType.PADEL: "padel", TrainrActivityType.HOME_GYM: "gym",
}


def _day(d: date) -> str:
    return f"{d.day} {MONTHS[d.month - 1]}"


def _num(value: Decimal, places: str = "0.1") -> str:
    return f"{value.quantize(Decimal(places), rounding=ROUND_HALF_UP).normalize():f}".replace(".", ",")


def _sets(value: Decimal) -> str:
    return f"{_num(value)} {'set' if value == 1 else 'sets'}"


def _dose(sets: int | None, reps: int | None, weight: Decimal | None, seconds: int | None) -> str:
    amount = f"{seconds} s" if seconds and not reps else f"{reps or '?'}"
    text = f"{sets or 1} × {amount}"
    return text + (f" × {_num(weight, '0.01')} kg" if weight else "")


def _session_table(targets: list[Target]) -> list[str]:
    """One row per exercise: what to do this time, what you did last time, and what changed."""
    lines = ["| Oefening | Deze keer | Vorige keer | Verandering |", "|---|---|---|---|"]
    for t in targets:
        last: Performance | None = t.last
        if last is None:
            previous = "–"
            change = "nieuw: kies een startgewicht" if trainr_plan_service.needs_weight(t) else "nieuw"
        else:
            previous = _dose(last.sets, last.reps, last.weight_kg, last.duration_seconds)
            change = t.change
        name = " ".join(t.exercise.name.replace("|", "/").split())
        lines.append(f"| **{name}** | {_dose(t.sets, t.reps, t.weight_kg, t.duration_seconds)} | {previous} | {change} |")
    return lines


def build_report(plan: WeekPlan, added: dict[str, bool], now: datetime) -> ParsedReport:
    sunday = plan.monday + timedelta(days=6)
    days = " · ".join(f"{DAYS[s.day.weekday()][:2]} {s.kind.title.lower()}" for s in plan.sessions)
    title = f"Weekplan {_day(plan.monday)} – {_day(sunday)}" + (f": {days}" if days else "")

    findings = []
    if plan.sessions_done == 0:
        findings.append(ReportFileItem(
            verdict=BriefrVerdict.WATCH, headline="Geen gym-sessies in de afgelopen 3 weken",
            detail="Het plan begint met 3 × 10; kies zelf startgewichten en vink de sessies af, dan rekent het volgende plan verder.",
        ))
    for group in plan.boosted:
        findings.append(ReportFileItem(
            verdict=BriefrVerdict.WATCH,
            headline=f"{GROUPS[group].capitalize()}: {_sets(plan.sets_per_week[group])} per week, het plan geeft {PLANNED_SETS[group]}",
            detail="Deze week 4 sets in plaats van 3 op de oefeningen voor deze spiergroep.",
        ))
    for exercise, last in plan.plateaus:
        findings.append(ReportFileItem(
            verdict=BriefrVerdict.WATCH,
            headline=f"{exercise.name}: drie keer gelijk ({_dose(last.sets, last.reps, last.weight_kg, last.duration_seconds)})",
            detail="Lukt de stap van deze week niet, probeer dan een variant van de oefening of een lichtere week.",
        ))

    added_count = sum(1 for was_added in added.values() if was_added)
    if plan.sessions:
        summary = (
            f"{len(plan.sessions)} sessies van zo'n 45 minuten"
            + (" staan in je planner." if added_count == len(plan.sessions) else " (al eerder in je planner gezet).")
        )
    else:
        summary = "Geen sessies voorgesteld: je week heeft al drie gym-sessies gepland."
    if plan.sessions_done:
        summary += (" Het verst achter: " + " en ".join(GROUPS[g] for g in plan.boosted) + ", die krijgen een set extra."
                    if plan.boosted else " Alle spiergroepen kregen de afgelopen 3 weken genoeg sets.")

    body = ["## De afgelopen 3 weken", ""]
    if plan.sessions_done:
        body.append(f"{plan.sessions_done} gym-sessies, gemiddeld {_num(Decimal(plan.sessions_done) / 3)} per week.")
        body.append("Sets per week per spiergroep (wat het plan geeft): " + ", ".join(
            f"{GROUPS[g]} {_num(plan.sets_per_week[g])} ({PLANNED_SETS[g]})" for g in PLANNED_SETS) + ".")
    else:
        body.append("Geen afgevinkte gym-sessies gevonden.")
    body += ["", "## Je week"]
    for session in plan.sessions:
        body += ["", f"### {DAYS[session.day.weekday()].capitalize()} {_day(session.day)}: {session.kind.title}",
                 *_session_table(session.targets)]
    if plan.sports or plan.taken_days:
        body += ["", "## Rond je andere sporten"]
        body += [f"- {DAYS[d.weekday()].capitalize()} {_day(d)}: {SPORTS.get(kind, kind.value)}" for d, kind in plan.sports]
        body += [f"- {DAYS[d.weekday()].capitalize()} {_day(d)}: je eigen gym-sessie, die blijft staan" for d in plan.taken_days]
        body.append("Geen gym op een sportdag, en de benen-sessie niet de dag ervoor.")
    body += ["", "## Hoe het plan rekent",
             "Spiergroei: 8 tot 12 herhalingen. Haal je 12, dan gaat het gewicht omhoog (2 kg bij dumbbells, "
             "2,5 kg bij een stang) en begin je weer bij 8; anders één herhaling meer. Lichaamsgewicht tot 15, "
             "dan een set extra. De sessies staan als voorstel in je planner: pas ze daar aan of verwijder ze."]
    if plan.notes:
        body += ["", *plan.notes]

    return ParsedReport(
        agent=AGENT, run_at=now, title=title[:200], summary=summary[:1000],
        attention=BriefrAttention.WATCH if findings else BriefrAttention.INFO,
        body="\n".join(body), items=findings,
    )


def run(db: Session, today: date, now: datetime) -> tuple[WeekPlan, int, str]:
    """Plans the week after `today`: adds the sessions to trainr's planner and writes the report.
    Returns the plan, how many sessions were added, and the report's outcome."""
    plan = trainr_plan_service.build_plan(db, today)
    outcomes = trainr_plan_service.add_to_planner(db, plan)
    added = {session.kind.key: was_added for session, was_added in outcomes}
    report = build_report(plan, added, now)
    outcome = briefr_report_service.save_generated_report(db, f"server/{AGENT}/{plan.monday.isoformat()}", report)
    return plan, sum(added.values()), outcome
