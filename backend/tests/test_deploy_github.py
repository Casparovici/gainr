import io
import json
import urllib.error

import pytest

from scripts import deploy_github as gh

SHA = "a" * 40


def run(workflow_id, status, conclusion=None, attempt=1, run_id=1, event="push"):
    return {
        "workflow_id": workflow_id, "status": status, "conclusion": conclusion, "run_attempt": attempt, "id": run_id,
        "event": event,
    }


def test_every_workflow_passing_is_success():
    assert gh.ci_verdict([run(1, "completed", "success"), run(2, "completed", "skipped")]) == "success"


def test_one_failing_workflow_is_failure_even_while_another_still_runs():
    assert gh.ci_verdict([run(1, "completed", "failure"), run(2, "in_progress")]) == "failure"
    assert gh.ci_verdict([run(1, "completed", "cancelled")]) == "failure"


def test_no_runs_yet_or_one_still_going_is_pending():
    assert gh.ci_verdict([]) == "pending"
    assert gh.ci_verdict([run(1, "completed", "success"), run(2, "queued")]) == "pending"


def test_only_the_runs_a_push_started_count():
    # Dependabot's update job runs on main's commit too ("dynamic"); its failing says nothing
    # about the commit, and a commit with only such runs is still waiting for CI.
    assert gh.ci_verdict([run(1, "completed", "success"), run(2, "completed", "failure", event="dynamic")]) == "success"
    assert gh.ci_verdict([run(2, "completed", "success", event="dynamic")]) == "pending"


def test_a_rerun_counts_by_its_latest_attempt():
    first = run(1, "completed", "failure", attempt=1, run_id=10)
    rerun = run(1, "completed", "success", attempt=2, run_id=10)
    assert gh.ci_verdict([first, rerun]) == "success"
    assert gh.ci_verdict([rerun, first]) == "success"


def test_without_a_token_ci_says_so_and_status_does_nothing(monkeypatch, capsys):
    monkeypatch.delenv("GAINR_DEPLOY_GITHUB_TOKEN", raising=False)
    monkeypatch.setattr(gh, "_request", lambda *a, **k: pytest.fail("no request without a token"))

    assert gh.main(["ci", SHA]) == 0
    assert capsys.readouterr().out.strip() == "no-token"
    assert gh.main(["status", SHA, "success", "Deployed"]) == 0


def test_ci_asks_for_the_commits_runs_with_the_token(monkeypatch, capsys):
    monkeypatch.setenv("GAINR_DEPLOY_GITHUB_TOKEN", "secret-token")
    seen = {}

    def fake_urlopen(request, timeout):
        seen["url"], seen["auth"] = request.full_url, request.get_header("Authorization")
        return io.BytesIO(json.dumps({"workflow_runs": [run(1, "completed", "success")]}).encode())

    monkeypatch.setattr(gh.urllib.request, "urlopen", fake_urlopen)
    assert gh.main(["ci", SHA]) == 0
    assert capsys.readouterr().out.strip() == "success"
    assert seen["url"] == f"https://api.github.com/repos/Casparovici/ipper/actions/runs?head_sha={SHA}&per_page=100"
    assert seen["auth"] == "Bearer secret-token"


def test_github_not_answering_is_an_error_for_ci_and_ignored_for_status(monkeypatch, capsys):
    monkeypatch.setenv("GAINR_DEPLOY_GITHUB_TOKEN", "secret-token")

    def down(request, timeout):
        raise urllib.error.URLError("no route")

    monkeypatch.setattr(gh.urllib.request, "urlopen", down)
    assert gh.main(["ci", SHA]) == 0
    assert capsys.readouterr().out.strip() == "error"
    assert gh.main(["status", SHA, "failure", "Health check failed"]) == 0


def test_status_posts_the_deploy_context(monkeypatch):
    monkeypatch.setenv("GAINR_DEPLOY_GITHUB_TOKEN", "secret-token")
    sent = {}

    def fake_urlopen(request, timeout):
        sent["url"], sent["method"], sent["body"] = request.full_url, request.method, json.loads(request.data)
        return io.BytesIO(b"{}")

    monkeypatch.setattr(gh.urllib.request, "urlopen", fake_urlopen)
    gh.main(["status", SHA, "success", "Deployed to homecloud"])
    assert sent["url"].endswith(f"/statuses/{SHA}") and sent["method"] == "POST"
    assert sent["body"] == {"state": "success", "context": "homecloud/deploy", "description": "Deployed to homecloud"}


def test_bad_arguments_are_refused_before_anything_is_sent(monkeypatch):
    monkeypatch.setenv("GAINR_DEPLOY_GITHUB_TOKEN", "secret-token")
    monkeypatch.setattr(gh, "_request", lambda *a, **k: pytest.fail("nothing sent"))
    assert gh.main(["ci", "not-a-sha"]) == 2
    assert gh.main(["status", SHA, "exploded", "x"]) == 2
    monkeypatch.setenv("GAINR_GITHUB_REPO", "../evil")
    assert gh.main(["ci", SHA]) == 2
