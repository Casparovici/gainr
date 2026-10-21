"""The deploy script's two questions for GitHub (docs/adr/0042): did CI pass on this commit, and
how did its deploy go. Standard library only, so it runs before anything is installed.

    python -m scripts.deploy_github ci <sha>
        Prints one word: success, pending, failure, error (GitHub didn't answer) or no-token.
    python -m scripts.deploy_github status <sha> <success|failure|pending> <description>
        Marks the commit on GitHub with a "homecloud/deploy" status. Quietly does nothing without
        a token, or if GitHub refuses: reporting must never fail a deploy.

The token is GAINR_DEPLOY_GITHUB_TOKEN (in /etc/gainr/deploy.env on the server), a fine-grained
token for this one repository with Actions: read and Commit statuses: read and write. Never print
it. The repository is GAINR_GITHUB_REPO, "Casparovici/ipper" unless set.
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request

API = "https://api.github.com"
DEFAULT_REPO = "Casparovici/ipper"
STATUS_CONTEXT = "homecloud/deploy"
TIMEOUT_SECONDS = 15
_SHA = re.compile(r"^[0-9a-f]{40}$")
_REPO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*$")
# A run that ended any of these ways passed; any other completed run failed.
_PASSED = {"success", "skipped", "neutral"}
# Only the runs a push to main starts are CI. Others on the same commit -- Dependabot's own
# update jobs ("dynamic"), a manual dispatch, a schedule -- say nothing about whether it's safe.
_CI_EVENTS = {"push"}


def _request(method: str, path: str, token: str, body: dict | None = None) -> dict:
    request = urllib.request.Request(
        f"{API}{path}",
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "gainr-deploy",
        },
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        return json.loads(response.read() or b"{}")


def ci_verdict(runs: list[dict]) -> str:
    """success when every workflow's latest push run on the commit passed, failure when one of
    them failed, pending while one is still going or none has started yet. A workflow re-run
    counts by its latest attempt, so re-running a flaky job unblocks the deploy."""
    latest: dict[int, dict] = {}
    for run in runs:
        workflow = run.get("workflow_id")
        if workflow is None or run.get("event", "push") not in _CI_EVENTS:
            continue
        seen = latest.get(workflow)
        if seen is None or (run.get("run_attempt", 1), run.get("id", 0)) > (seen.get("run_attempt", 1), seen.get("id", 0)):
            latest[workflow] = run
    if not latest:
        return "pending"
    if any(r.get("status") == "completed" and r.get("conclusion") not in _PASSED for r in latest.values()):
        return "failure"
    if all(r.get("status") == "completed" for r in latest.values()):
        return "success"
    return "pending"


def ci(sha: str, token: str, repo: str) -> str:
    try:
        body = _request("GET", f"/repos/{repo}/actions/runs?head_sha={sha}&per_page=100", token)
    except (urllib.error.URLError, TimeoutError, ValueError):
        return "error"
    runs = body.get("workflow_runs")
    return ci_verdict(runs) if isinstance(runs, list) else "error"


def post_status(sha: str, state: str, description: str, token: str, repo: str) -> None:
    try:
        _request(
            "POST",
            f"/repos/{repo}/statuses/{sha}",
            token,
            {"state": state, "context": STATUS_CONTEXT, "description": description[:140]},
        )
    except (urllib.error.URLError, TimeoutError, ValueError):
        pass


def main(argv: list[str]) -> int:
    token = os.environ.get("GAINR_DEPLOY_GITHUB_TOKEN", "").strip()
    repo = os.environ.get("GAINR_GITHUB_REPO", DEFAULT_REPO)
    if len(argv) < 2 or argv[0] not in ("ci", "status") or not _SHA.match(argv[1]) or not _REPO.match(repo):
        print(__doc__, file=sys.stderr)
        return 2
    command, sha = argv[0], argv[1]
    if command == "ci":
        print(ci(sha, token, repo) if token else "no-token")
        return 0
    if len(argv) != 4 or argv[2] not in ("success", "failure", "pending"):
        print(__doc__, file=sys.stderr)
        return 2
    if token:
        post_status(sha, argv[2], argv[3], token, repo)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
