import json
from datetime import datetime
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.db import get_db
from app.models.asset import Asset
from app.models.briefr_report import BriefrAttention, BriefrVerdict
from app.repositories import briefr_report_repo
from app.routers import briefr as briefr_router
from app.services import briefr_report_service
from app.services.briefr_report_service import InvalidReport, parse_report
from scripts import import_briefr_reports

PATH = "reports/holdings-scan/2026-10-19.md"

REPORT = """+++
agent = "holdings-scan"
run_at = 2026-10-19T02:14:00+02:00
title = "Nightly scan"
summary = "ASML guidance cut."

[[items]]
symbol = "ASML"
verdict = "act"
headline = "Q3 guidance lowered"
sources = ["https://example.com/asml"]

[[items]]
ticker = "NVDA"
verdict = "watch"
headline = "Earnings on Wednesday"

[[items]]
verdict = "ignore"
headline = "Nothing new on the rest"
+++
# What happened

ASML lowered its **guidance**.
"""


def write(root: Path, path: str, text: str) -> Path:
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    return target


def header(**over) -> str:
    fields = {"agent": '"holdings-scan"', "run_at": "2026-10-19T02:14:00Z", "title": '"Scan"', **over}
    return "+++\n" + "\n".join(f"{k} = {v}" for k, v in fields.items()) + "\n+++\nBody"


@pytest.fixture()
def assets(db_session):
    asml = Asset(ticker="ASML", name="ASML Holding", yahoo_symbol="ASML.AS")
    nvda = Asset(ticker="NVDA", name="NVIDIA", yahoo_symbol="NVDA")
    db_session.add_all([asml, nvda])
    db_session.flush()
    return {"ASML": asml, "NVDA": nvda}


@pytest.fixture()
def client(db_session):
    app = FastAPI()
    app.include_router(briefr_router.router)
    app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(app)


# -- reading a report file -------------------------------------------------------------------------


def test_a_report_file_is_read_into_its_header_findings_and_write_up():
    report = parse_report(PATH, REPORT)

    assert report.agent == "holdings-scan"
    assert report.run_at == datetime(2026, 10, 19, 0, 14)  # stored as UTC
    assert (report.title, report.summary) == ("Nightly scan", "ASML guidance cut.")
    assert [(i.symbol, i.verdict) for i in report.items] == [
        ("ASML", BriefrVerdict.ACT), ("NVDA", BriefrVerdict.WATCH), (None, BriefrVerdict.IGNORE),
    ]
    assert report.items[0].sources == ["https://example.com/asml"]
    assert report.body == "# What happened\n\nASML lowered its **guidance**."


def test_a_report_is_never_calmer_than_its_most_urgent_finding():
    assert parse_report(PATH, REPORT).attention == BriefrAttention.ACT
    declared_info = REPORT.replace('summary = "ASML guidance cut."', 'attention = "info"')
    assert parse_report(PATH, declared_info).attention == BriefrAttention.ACT
    assert parse_report(PATH, header(attention='"watch"')).attention == BriefrAttention.WATCH
    assert parse_report(PATH, header()).attention == BriefrAttention.INFO


def test_windows_line_endings_a_byte_order_mark_and_unknown_keys_are_fine():
    report = parse_report(PATH, "﻿" + header(model='"whatever"').replace("\n", "\r\n"))
    assert (report.title, report.body) == ("Scan", "Body")


@pytest.mark.parametrize(
    ("path", "text", "problem"),
    [
        ("reports/holdings-scan/notes.txt", header(), "reports/<agent>/<name>.md"),
        ("elsewhere/holdings-scan/a.md", header(), "reports/<agent>/<name>.md"),
        ("reports/Holdings/a.md", header(), "reports/<agent>/<name>.md"),
        (PATH, "# no header", "starts with a +++ line"),
        (PATH, "+++\ntitle = 'x'\n", "isn't closed"),
        (PATH, "+++\ntitle = \n+++\n", "isn't valid TOML"),
        ("reports/app-builder/a.md", header(), "file is in reports/app-builder/"),
        (PATH, header(run_at="2026-10-19T02:14:00"), "needs a UTC offset"),
        (PATH, header(title='"   "'), "title"),
        (PATH, header(attention='"panic"'), "attention"),
        (PATH, header().replace("+++\nBody", '[[items]]\nverdict = "maybe"\nheadline = "x"\n+++\n'), "items.0.verdict"),
        (PATH, header().replace("+++\nBody", '[[items]]\nverdict = "act"\nheadline = "x"\nsources = ["javascript:alert(1)"]\n+++\n'), "not an http(s) link"),
    ],
)
def test_a_file_that_breaks_the_contract_says_why(path, text, problem):
    with pytest.raises(InvalidReport, match=None) as raised:
        parse_report(path, text)
    assert problem in str(raised.value)


def test_a_write_up_over_the_limit_is_refused():
    with pytest.raises(InvalidReport, match="longer than"):
        parse_report(PATH, header().replace("Body", "x" * (briefr_report_service.MAX_BODY_CHARS + 1)))


# -- importing the repository ----------------------------------------------------------------------


def test_importing_creates_reports_and_links_findings_to_assets_by_ticker_or_yahoo_symbol(db_session, assets, tmp_path):
    write(tmp_path, PATH, REPORT.replace('symbol = "ASML"', 'symbol = "asml.as"'))

    result = briefr_report_service.import_reports(db_session, tmp_path)

    assert (result.created, result.updated, result.unchanged, result.failed) == (1, 0, 0, [])
    [report] = briefr_report_repo.list_reports(db_session)
    assert report.source_path == PATH
    assert [i.asset_id for i in report.items] == [assets["ASML"].id, assets["NVDA"].id, None]
    assert json.loads(report.items[0].sources) == ["https://example.com/asml"]


def test_reimporting_skips_unchanged_files_and_a_rewritten_one_replaces_its_report_unread(db_session, assets, tmp_path):
    target = write(tmp_path, PATH, REPORT)
    briefr_report_service.import_reports(db_session, tmp_path)
    [report] = briefr_report_repo.list_reports(db_session)
    briefr_report_service.set_read(db_session, report, True, now=datetime(2026, 10, 19, 7))

    assert briefr_report_service.import_reports(db_session, tmp_path).unchanged == 1
    assert report.read_at is not None

    target.write_text(REPORT.replace("Nightly scan", "Nightly scan (corrected)").split("[[items]]")[0] + "+++\n")
    result = briefr_report_service.import_reports(db_session, tmp_path)

    assert (result.created, result.updated) == (0, 1)
    [again] = briefr_report_repo.list_reports(db_session)
    assert again.id == report.id
    assert (again.title, again.items, again.read_at) == ("Nightly scan (corrected)", [], None)
    assert again.attention == BriefrAttention.INFO


def test_a_bad_file_is_listed_and_the_others_still_import(db_session, assets, tmp_path):
    write(tmp_path, PATH, REPORT)
    write(tmp_path, "reports/holdings-scan/broken.md", "no header")
    write(tmp_path, "reports/holdings-scan/README.md", "How this agent reports")
    write(tmp_path, "reports/README.md", "Not a report")
    (tmp_path / "reports/holdings-scan/latin1.md").write_bytes("+++\ntitle = 'caf\xe9'\n+++\n".encode("latin-1"))
    write(tmp_path, "reports/holdings-scan/huge.md", "x" * (briefr_report_service.MAX_FILE_BYTES + 1))

    result = briefr_report_service.import_reports(db_session, tmp_path)

    assert result.created == 1
    assert sorted(result.failed) == [
        ("reports/holdings-scan/broken.md", "A report starts with a +++ line, then its TOML header"),
        ("reports/holdings-scan/huge.md", "Larger than 256 KB"),
        ("reports/holdings-scan/latin1.md", "Not UTF-8 text"),
    ]


def test_symlinks_are_not_followed(db_session, tmp_path):
    outside = write(tmp_path / "outside", "secret.md", REPORT)
    repo = tmp_path / "repo"
    (repo / "reports/holdings-scan").mkdir(parents=True)
    (repo / "reports/holdings-scan/2026-10-19.md").symlink_to(outside)

    result = briefr_report_service.import_reports(db_session, repo)

    assert result.created == 0
    assert result.failed == [(PATH, "Not a regular file (symlinks aren't followed)")]


def test_a_checkout_without_reports_imports_nothing(db_session, tmp_path):
    assert briefr_report_service.import_reports(db_session, tmp_path).created == 0


def test_the_import_script_reads_a_checkout_and_needs_one(db_session, tmp_path, monkeypatch, capsys):
    write(tmp_path, PATH, REPORT)
    monkeypatch.setattr(import_briefr_reports, "SessionLocal", lambda: _Unclosed(db_session))

    assert import_briefr_reports.main([str(tmp_path)]) == 0
    assert "1 new" in capsys.readouterr().out
    assert len(briefr_report_repo.list_reports(db_session)) == 1
    assert import_briefr_reports.main([str(tmp_path / "missing")]) == 2
    monkeypatch.setattr(import_briefr_reports, "BRIEFR_REPO_DIR", None)
    assert import_briefr_reports.main([]) == 2


class _Unclosed:
    """The test's session, with close() a no-op so the script can't end it."""

    def __init__(self, session):
        self._session = session

    def __getattr__(self, name):
        return getattr(self._session, name)

    def close(self):
        pass


# -- the reader's side -----------------------------------------------------------------------------


def _import(db_session, tmp_path, *files: tuple[str, str]):
    for path, text in files:
        write(tmp_path, path, text)
    briefr_report_service.import_reports(db_session, tmp_path)
    db_session.commit()


def test_archiving_reads_the_report_and_unarchiving_keeps_it_read(db_session, tmp_path):
    _import(db_session, tmp_path, (PATH, REPORT))
    [report] = briefr_report_repo.list_reports(db_session)
    first = datetime(2026, 10, 19, 7)

    briefr_report_service.set_archived(db_session, report, True, now=first)
    briefr_report_service.set_archived(db_session, report, True, now=datetime(2026, 10, 19, 8))
    assert (report.archived_at, report.read_at) == (first, first)

    briefr_report_service.set_archived(db_session, report, False, now=datetime(2026, 10, 19, 9))
    assert (report.archived_at, report.read_at) == (None, first)

    briefr_report_service.set_read(db_session, report, False, now=datetime(2026, 10, 19, 10))
    assert report.read_at is None


def test_the_inbox_lists_newest_first_with_counts_and_filters(client, db_session, assets, tmp_path):
    _import(
        db_session, tmp_path,
        (PATH, REPORT),
        ("reports/holdings-scan/2026-10-18.md", header(run_at="2026-10-18T02:00:00Z", title='"Quiet night"')),
        ("reports/app-builder/2026-10-19.md", header(agent='"app-builder"', run_at="2026-10-19T03:00:00Z", title='"PR #31"')),
    )

    inbox = client.get("/api/briefr/reports").json()
    assert [r["title"] for r in inbox] == ["PR #31", "Nightly scan", "Quiet night"]
    scan = inbox[1]
    assert scan["run_at"] == "2026-10-19T00:14:00Z"
    assert (scan["attention"], scan["is_read"], scan["is_archived"]) == ("act", False, False)
    assert scan["counts"] == {"act": 1, "watch": 1, "ignore": 1}
    assert "body" not in scan

    assert [r["title"] for r in client.get("/api/briefr/reports?agent=app-builder").json()] == ["PR #31"]
    assert [r["title"] for r in client.get("/api/briefr/reports?attention=act").json()] == ["Nightly scan"]
    assert [r["title"] for r in client.get(f"/api/briefr/reports?asset_id={assets['NVDA'].id}").json()] == ["Nightly scan"]
    assert len(client.get("/api/briefr/reports?limit=1").json()) == 1
    assert client.get("/api/briefr/reports?limit=0").status_code == 422


def test_a_report_opens_with_its_write_up_and_findings_and_is_triaged(client, db_session, assets, tmp_path):
    _import(db_session, tmp_path, (PATH, REPORT))
    report_id = client.get("/api/briefr/reports").json()[0]["id"]

    detail = client.get(f"/api/briefr/reports/{report_id}").json()
    assert detail["body"].startswith("# What happened")
    assert detail["source_path"] == PATH
    assert [(i["symbol"], i["asset_id"], i["verdict"]) for i in detail["items"]] == [
        ("ASML", assets["ASML"].id, "act"), ("NVDA", assets["NVDA"].id, "watch"), (None, None, "ignore"),
    ]
    assert detail["items"][0]["sources"] == ["https://example.com/asml"]

    assert client.put(f"/api/briefr/reports/{report_id}/read", json={"is_read": True}).json()["is_read"] is True
    assert client.get("/api/briefr/reports?unread=true").json() == []

    archived = client.put(f"/api/briefr/reports/{report_id}/archived", json={"is_archived": True}).json()
    assert archived["is_archived"] is True
    assert client.get("/api/briefr/reports").json() == []
    assert [r["id"] for r in client.get("/api/briefr/reports?archived=true").json()] == [report_id]

    assert client.get("/api/briefr/reports/999").status_code == 404
    assert client.put("/api/briefr/reports/999/read", json={"is_read": True}).status_code == 404


def test_agents_are_listed_with_their_last_run_and_unread_count(client, db_session, tmp_path):
    _import(
        db_session, tmp_path,
        (PATH, REPORT),
        ("reports/holdings-scan/2026-10-18.md", header(run_at="2026-10-18T02:00:00Z")),
        ("reports/app-builder/2026-10-19.md", header(agent='"app-builder"', run_at="2026-10-19T03:00:00Z")),
    )
    newest = client.get("/api/briefr/reports?agent=holdings-scan").json()[0]["id"]
    client.put(f"/api/briefr/reports/{newest}/read", json={"is_read": True})

    assert client.get("/api/briefr/agents").json() == [
        {"agent": "app-builder", "last_run_at": "2026-10-19T03:00:00Z", "report_count": 1, "unread_count": 1},
        {"agent": "holdings-scan", "last_run_at": "2026-10-19T00:14:00Z", "report_count": 2, "unread_count": 1},
    ]
