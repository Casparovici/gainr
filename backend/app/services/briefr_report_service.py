"""briefr: reading the report files agents commit to the agents repository, and the reader's own
state on them (docs/adr/0044-briefr-agent-reports.md).

A report file is Markdown under `reports/<agent>/`, opening with a TOML header fenced by `+++`
lines (the agent, when it ran, a title and its findings, each with a verdict), then the write-up.
Agents never call the app: a timer on the server pulls the repository and `import_reports` reads
it, so nothing new is reachable from the internet. Re-importing is idempotent per file; a file the
agent rewrote replaces its report and makes it unread again. A file that is gone from the
repository leaves its report alone: the app is where reports are kept, the repository is only how
they arrive."""

import hashlib
import json
import re
import tomllib
from dataclasses import dataclass, field
from datetime import date as date_, datetime, timezone
from pathlib import Path, PurePosixPath

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.models.briefr_report import BriefrAttention, BriefrReport, BriefrReportItem, BriefrVerdict
from app.repositories import asset_repo, briefr_report_repo
from app.schemas.briefr import (
    BriefrAgentOut,
    BriefrIngredientOut,
    BriefrItemOut,
    BriefrRecipeOut,
    BriefrReportDetailOut,
    BriefrReportOut,
    ReportFileFront,
    ReportFileItem,
    ReportFileRecipe,
    VerdictCountsOut,
)

FENCE = "+++"
REPORTS_DIR = "reports"
MAX_FILE_BYTES = 256 * 1024
MAX_BODY_CHARS = 100_000
_FILE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,120}\.md$")
_AGENT_DIR = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")

# A report is never calmer than its most urgent finding.
_RANK = {BriefrAttention.INFO: 0, BriefrAttention.WATCH: 1, BriefrAttention.ACT: 2}
_VERDICT_ATTENTION = {
    BriefrVerdict.ACT: BriefrAttention.ACT,
    BriefrVerdict.WATCH: BriefrAttention.WATCH,
    BriefrVerdict.IGNORE: BriefrAttention.INFO,
}


class InvalidReport(ValueError):
    """A report file that can't be imported. The message says what's wrong with it."""


@dataclass(frozen=True)
class ParsedReport:
    agent: str
    run_at: datetime  # UTC, naive
    title: str
    summary: str | None
    attention: BriefrAttention
    body: str
    items: list[ReportFileItem]


@dataclass
class ImportResult:
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    # (path relative to the repository, what's wrong with it)
    failed: list[tuple[str, str]] = field(default_factory=list)


def _validation_message(exc: ValidationError) -> str:
    def where(loc: tuple) -> str:
        return ".".join(str(part) for part in loc) or "header"

    return "; ".join(f"{where(e['loc'])}: {e['msg']}" for e in exc.errors()[:5])


def parse_report(source_path: str, text: str) -> ParsedReport:
    """Reads one report file. `source_path` is its path in the repository; the agent folder it's
    in must be the agent its header names, so one agent can't file a report as another."""
    parts = PurePosixPath(source_path).parts
    if len(parts) != 3 or parts[0] != REPORTS_DIR or not _AGENT_DIR.match(parts[1]) or not _FILE_NAME.match(parts[2]):
        raise InvalidReport("A report lives at reports/<agent>/<name>.md")

    text = text.lstrip("﻿").replace("\r\n", "\n")
    lines = text.split("\n")
    if not lines or lines[0].strip() != FENCE:
        raise InvalidReport(f"A report starts with a {FENCE} line, then its TOML header")
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == FENCE)
    except StopIteration:
        raise InvalidReport(f"The header isn't closed by a second {FENCE} line") from None

    try:
        header = tomllib.loads("\n".join(lines[1:end]))
    except tomllib.TOMLDecodeError as exc:
        raise InvalidReport(f"The header isn't valid TOML: {exc}") from exc
    try:
        front = ReportFileFront.model_validate(header)
    except ValidationError as exc:
        raise InvalidReport(_validation_message(exc)) from exc
    if front.agent != parts[1]:
        raise InvalidReport(f"The header says agent {front.agent!r}, but the file is in reports/{parts[1]}/")

    body = "\n".join(lines[end + 1:]).strip()
    if len(body) > MAX_BODY_CHARS:
        raise InvalidReport(f"The write-up is longer than {MAX_BODY_CHARS} characters")

    attention = max(
        [front.attention or BriefrAttention.INFO, *(_VERDICT_ATTENTION[i.verdict] for i in front.items)],
        key=_RANK.__getitem__,
    )
    return ParsedReport(
        agent=front.agent,
        run_at=front.run_at.astimezone(timezone.utc).replace(tzinfo=None),
        title=front.title,
        summary=front.summary,
        attention=attention,
        body=body,
        items=front.items,
    )


def save_report(db: Session, source_path: str, content_hash: str, parsed: ParsedReport) -> tuple[BriefrReport, bool]:
    """Creates the report for `source_path`, or replaces the one already there (findings and all)
    and makes it unread again. Returns the report and whether it is new."""
    symbols: dict[str, int | None] = {}

    def asset_id_for(symbol: str | None) -> int | None:
        if symbol is None:
            return None
        if symbol not in symbols:
            asset = asset_repo.get_by_symbol(db, symbol)
            symbols[symbol] = asset.id if asset else None
        return symbols[symbol]

    items = [
        BriefrReportItem(
            sort_order=n,
            symbol=item.symbol,
            asset_id=asset_id_for(item.symbol),
            verdict=item.verdict,
            headline=item.headline,
            detail=item.detail,
            sources=json.dumps(item.sources),
            recipe=item.recipe.model_dump_json() if item.recipe is not None else None,
        )
        for n, item in enumerate(parsed.items)
    ]
    fields = dict(
        content_hash=content_hash,
        agent=parsed.agent,
        run_at=parsed.run_at,
        title=parsed.title,
        summary=parsed.summary,
        body=parsed.body,
        attention=parsed.attention,
    )
    existing = briefr_report_repo.get_by_source_path(db, source_path)
    if existing is None:
        return briefr_report_repo.create_report(db, source_path=source_path, items=items, **fields), True
    return briefr_report_repo.update_report(db, existing, items=items, read_at=None, **fields), False


def save_generated_report(db: Session, source_path: str, parsed: ParsedReport) -> str:
    """Saves a report the server wrote itself (no file behind it, e.g. the performance reports),
    under `source_path` as its key. Its hash covers the content but not `run_at`, so writing the
    same report again changes nothing and leaves it read. Returns "created", "updated" or
    "unchanged"."""
    content = json.dumps(
        [parsed.agent, parsed.title, parsed.summary, parsed.attention.value, parsed.body,
         [item.model_dump(mode="json") for item in parsed.items]],
        sort_keys=True,
    )
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    existing = briefr_report_repo.get_by_source_path(db, source_path)
    if existing is not None and existing.content_hash == content_hash:
        return "unchanged"
    _, created = save_report(db, source_path, content_hash, parsed)
    return "created" if created else "updated"


def import_reports(db: Session, root: Path) -> ImportResult:
    """Imports every report file in the repository checked out at `root`: new files become
    reports, changed ones replace theirs, unchanged ones are skipped by their hash. A file that
    can't be read is reported in `failed` and doesn't stop the others. Symlinks aren't followed,
    so a report can only ever be a file inside the repository."""
    result = ImportResult()
    root = root.resolve()
    reports = root / REPORTS_DIR
    if not reports.is_dir():
        return result
    for path in sorted(reports.glob("*/*.md")):
        source_path = path.relative_to(root).as_posix()
        if path.name.lower() == "readme.md":
            continue
        if path.is_symlink() or path.parent.is_symlink() or not path.is_file():
            result.failed.append((source_path, "Not a regular file (symlinks aren't followed)"))
            continue
        if path.stat().st_size > MAX_FILE_BYTES:
            result.failed.append((source_path, f"Larger than {MAX_FILE_BYTES // 1024} KB"))
            continue
        raw = path.read_bytes()
        content_hash = hashlib.sha256(raw).hexdigest()
        existing = briefr_report_repo.get_by_source_path(db, source_path)
        if existing is not None and existing.content_hash == content_hash:
            result.unchanged += 1
            continue
        try:
            parsed = parse_report(source_path, raw.decode("utf-8"))
        except UnicodeDecodeError:
            result.failed.append((source_path, "Not UTF-8 text"))
            continue
        except InvalidReport as exc:
            result.failed.append((source_path, str(exc)))
            continue
        _, created = save_report(db, source_path, content_hash, parsed)
        if created:
            result.created += 1
        else:
            result.updated += 1
    return result


# -- the reader's side -----------------------------------------------------------------------------


def set_read(db: Session, report: BriefrReport, is_read: bool, now: datetime) -> BriefrReport:
    """Marking read stamps the first moment; marking unread clears it."""
    if not is_read:
        return briefr_report_repo.update_report(db, report, read_at=None)
    if report.read_at is None:
        return briefr_report_repo.update_report(db, report, read_at=now)
    return report


def set_archived(db: Session, report: BriefrReport, is_archived: bool, now: datetime) -> BriefrReport:
    """Archiving takes a report out of the inbox, and counts as having read it; un-archiving puts
    it back, still read."""
    if not is_archived:
        return briefr_report_repo.update_report(db, report, archived_at=None)
    fields = {}
    if report.archived_at is None:
        fields["archived_at"] = now
    if report.read_at is None:
        fields["read_at"] = now
    return briefr_report_repo.update_report(db, report, **fields) if fields else report


def _utc(moment: datetime) -> datetime:
    return moment.replace(tzinfo=timezone.utc)


def report_out(report: BriefrReport) -> BriefrReportOut:
    counts = {verdict: 0 for verdict in BriefrVerdict}
    for item in report.items:
        counts[item.verdict] += 1
    return BriefrReportOut(
        id=report.id,
        agent=report.agent,
        run_at=_utc(report.run_at),
        title=report.title,
        summary=report.summary,
        attention=report.attention,
        is_read=report.read_at is not None,
        is_archived=report.archived_at is not None,
        counts=VerdictCountsOut(
            act=counts[BriefrVerdict.ACT], watch=counts[BriefrVerdict.WATCH], ignore=counts[BriefrVerdict.IGNORE],
        ),
    )


def item_recipe(item: BriefrReportItem) -> ReportFileRecipe | None:
    """The recipe a finding suggests, as it was validated on import."""
    return ReportFileRecipe.model_validate_json(item.recipe) if item.recipe else None


# What a suggested recipe became in listr: (the recipe's id, the days it's planned on), per item id.
RecipeStates = dict[int, tuple[int | None, list[date_]]]


def item_out(item: BriefrReportItem, recipe_states: RecipeStates | None = None) -> BriefrItemOut:
    recipe = item_recipe(item)
    recipe_out = None
    if recipe is not None:
        listr_recipe_id, planned_on = (recipe_states or {}).get(item.id, (None, []))
        recipe_out = BriefrRecipeOut(
            url=recipe.url,
            servings=recipe.servings,
            minutes=recipe.minutes,
            ingredients=[BriefrIngredientOut(**i.model_dump()) for i in recipe.ingredients],
            steps=recipe.steps,
            listr_recipe_id=listr_recipe_id,
            planned_on=planned_on,
        )
    return BriefrItemOut(
        id=item.id,
        symbol=item.symbol,
        asset_id=item.asset_id,
        verdict=item.verdict,
        headline=item.headline,
        detail=item.detail,
        sources=json.loads(item.sources or "[]"),
        recipe=recipe_out,
    )


def report_detail_out(report: BriefrReport, recipe_states: RecipeStates | None = None) -> BriefrReportDetailOut:
    return BriefrReportDetailOut(
        **report_out(report).model_dump(),
        source_path=report.source_path,
        body=report.body,
        items=[item_out(item, recipe_states) for item in report.items],
    )


def list_agents(db: Session) -> list[BriefrAgentOut]:
    return [
        BriefrAgentOut(agent=agent, last_run_at=_utc(last_run), report_count=count, unread_count=unread or 0)
        for agent, last_run, count, unread in briefr_report_repo.agent_stats(db)
    ]
