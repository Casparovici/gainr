"""Writes the context briefr's agents work from into a checkout of the agents repository, and with
--push commits and pushes it: context/holdings.md (tickers, names and weights, no amounts) and
context/news.md (each holding's recent headlines from the feeds its News card reads) and
context/listr-products.md (listr's product catalog, for the home chef's recipes). See
briefr_context_service and docs/adr/0044-briefr-agent-reports.md.

Runs nightly from deploy/briefr-context.timer, before the agents' scheduled runs. Commits only when
a file changed, so a quiet night adds no commit.

Usage (from backend/):
    python -m scripts.export_briefr_context [--push] [REPO_DIR]
REPO_DIR defaults to GAINR_BRIEFR_REPO_DIR.
"""

import argparse
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import BRIEFR_REPO_DIR  # noqa: E402
from app.db import SessionLocal  # noqa: E402
from app.services import briefr_context_service  # noqa: E402

# Who the server's commits are by, without needing a git identity configured for its user.
IDENTITY = ["-c", "user.name=homecloud", "-c", "user.email=homecloud@users.noreply.github.com"]


def git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *IDENTITY, "-C", str(repo), *args], capture_output=True, text=True, timeout=120)


CONTEXT_PATHS = (
    briefr_context_service.HOLDINGS_PATH, briefr_context_service.NEWS_PATH, briefr_context_service.PRODUCTS_PATH,
)


def push(repo: Path, as_of: date) -> bool:
    """Commits the context files if they changed and pushes, pulling first so an agent's report
    pushed in the meantime doesn't get the push refused. True when there's nothing left to do."""
    git(repo, "add", *CONTEXT_PATHS)
    if git(repo, "diff", "--cached", "--quiet").returncode == 0:
        print("briefr context: unchanged")
        return True
    committed = git(repo, "commit", "--quiet", "-m", f"context: holdings, news and products as of {as_of.isoformat()}")
    if committed.returncode != 0:
        print(f"git commit failed: {committed.stderr.strip()}", file=sys.stderr)
        return False
    for step in (("pull", "--rebase", "--quiet"), ("push", "--quiet")):
        completed = git(repo, *step)
        if completed.returncode != 0:
            print(f"git {step[0]} failed: {completed.stderr.strip()}", file=sys.stderr)
            return False
    print(f"briefr context: pushed holdings, news and products as of {as_of.isoformat()}")
    return True


def main(argv: list[str] | None = None, now: datetime | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export briefr's agent context into the agents repository.")
    parser.add_argument("repo", nargs="?", default=BRIEFR_REPO_DIR, help="checkout of the agents repository")
    parser.add_argument("--push", action="store_true", help="commit and push the file if it changed")
    args = parser.parse_args(argv)
    if not args.repo or not Path(args.repo).is_dir():
        print("No repository: pass the path of a checkout or set GAINR_BRIEFR_REPO_DIR", file=sys.stderr)
        return 2
    repo = Path(args.repo)
    now = now or datetime.now(timezone.utc)
    as_of = now.astimezone().date()  # the server's own calendar day

    if args.push:
        # Start from what's on GitHub, so the commit below lands on top of last night's reports.
        git(repo, "pull", "--ff-only", "--quiet")
    db = SessionLocal()
    try:
        files = {
            briefr_context_service.HOLDINGS_PATH: briefr_context_service.holdings_markdown(db, as_of),
            briefr_context_service.NEWS_PATH: briefr_context_service.news_markdown(db, now),
            briefr_context_service.PRODUCTS_PATH: briefr_context_service.products_markdown(db),
        }
        db.commit()  # the valuations and news lookups may have cached what they fetched
    finally:
        db.close()
    for path, text in files.items():
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    if not args.push:
        print(f"briefr context: wrote {', '.join(files)} in {repo}")
        return 0
    return 0 if push(repo, as_of) else 1


if __name__ == "__main__":
    sys.exit(main())
