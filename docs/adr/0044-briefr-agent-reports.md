# 44. briefr: agent reports arrive as files in a private repository, pulled by the server

## Status

Accepted, with an addendum (2026-10-19) that adds the holdings' headlines to the agents' context.
Phase 1 (the module, the import, the context export) is built; the agents themselves and the later
phases are under "What comes next".

## Context

The user is setting up a set of AI agents that run unattended, mostly at night: a nightly scan of
the ~39 holdings (news, filings, earnings, sorted into act / watch / ignore), a nightly app builder
that turns one small backlog issue into a pull request, and more later. Their results need one
place to land, read over coffee, instead of scattered emails and chat threads. That place should
be the home server, inside this app, kept with everything else the household uses.

Two constraints shape it. The agents run as Claude scheduled tasks in the cloud (cheaper to run
and nothing to maintain), and the app is reachable only over Tailscale and the home LAN (ADR 0008):
a cloud agent can't call it. And what an agent writes was produced after reading the open web, so
it's untrusted text that ends up in front of the reader.

## Decisions

**A seventh module, briefr, not part of gainr.** Reports aren't only about investments: an app
builder's run is a report too, and so will later agents' be. briefr sits next to the others like
taskr does, a cross-cutting module with its own brand colour (teal), and reaches into gainr only
through its repositories: a finding about a holding is linked to its asset on import
(`asset_repo.get_by_symbol`), so it can link to the position. It is English, like gainr.

**Reports arrive as Markdown files in a private GitHub repository, and the server pulls them.**
Each agent commits `reports/<agent>/<name>.md` to the agents repository (separate from this one,
whose `main` deploys itself). `briefr-import.timer` pulls that repository every 10 minutes with a
deploy key and `scripts/import_briefr_reports.py` imports what's new. There is deliberately no
endpoint that creates a report: nothing new is reachable from the internet, and an agent's access
is a write key to one repository, not to the app or the database. The repository also keeps every
report as a file, readable even when the app isn't.

**The file is the contract.** A report starts with a TOML header fenced by `+++` lines, then the
write-up in the journal's Markdown subset:

```text
+++
agent = "holdings-scan"                 # must match the folder it's in
run_at = 2026-10-19T02:14:00+02:00      # with a UTC offset
title = "Nightly scan: 1 to act on"     # up to 200 characters
summary = "ASML cut its guidance."      # optional, up to 1000
attention = "watch"                     # optional: act | watch | info

[[items]]                               # optional, up to 200 findings
symbol = "ASML"                         # optional: the Ticker from context/holdings.md
verdict = "act"                         # act | watch | ignore
headline = "Q3 guidance lowered"        # up to 300 characters
detail = "Second cut this year."        # optional, up to 5000
sources = ["https://…"]                 # optional, up to 10 http(s) links
+++
The write-up, up to 100,000 characters.
```

TOML rather than YAML because Python reads it without a new dependency (`tomllib`), and its
parser is strict. A report is never calmer than its most urgent finding: an "act" finding makes
the report "act" whatever its header says. Unknown keys are ignored rather than refused, so an
agent that adds a field doesn't lose a night's report over it.

**Imports are idempotent per file.** `source_path` is unique and `content_hash` (SHA-256 of the
file) lets an unchanged file be skipped. A file the agent rewrote replaces its report, findings
and all, and makes it unread again. A file deleted from the repository leaves its report: the app
is where reports are kept, the repository is only how they arrive. A file that can't be read is
listed in the import's output and skipped; the others still import.

**The import treats every file as untrusted.** Symlinks aren't followed, a file over 256 KB is
skipped, every field is bounded, links must be http(s), and the write-up is rendered by
`MarkdownLite`, which never touches `innerHTML` and has no link syntax. Source links open in a new
tab with `rel="noopener noreferrer"`.

**Agents get their context from the same repository.** `briefr-context.timer` runs
`scripts/export_briefr_context.py` at 01:30 Amsterdam time: it writes `context/holdings.md`, one
table per portfolio with each holding's ticker, Yahoo symbol, name, class, weight and target
weight, plus the cash weight, and commits it if it changed. Weights only: no amounts, quantities
or balances leave the server. The user agreed to that line explicitly.

**Reading and archiving are the reader's own state**, kept in the app (`read_at`, `archived_at`),
never written back to the repository. Opening a report marks it read; archiving moves it out of
the inbox and counts as reading it.

## Schema

- `briefr_reports`: `source_path` (unique), `content_hash`, `agent`, `run_at` (UTC), `title`,
  `summary`, `body`, `attention` (act / watch / info), `read_at`, `archived_at`.
- `briefr_report_items`: `report_id`, `sort_order`, `symbol`, `asset_id` (nullable, resolved on
  import by ticker, else by a Yahoo symbol only one asset has), `verdict` (act / watch / ignore),
  `headline`, `detail`, `sources` (a JSON list in Text, like `Asset.news_sources`).

## Alternatives considered

- **An ingestion endpoint on its own Tailscale Funnel port**, with a bearer token, like the ICS
  feed (ADR 0007): agents could post directly, without the wait. But it would be the first public
  endpoint that writes, so a leaked token puts arbitrary text in the app; the pull adds at most
  ten minutes to a report nobody reads before morning.
- **Running the agents on the home server** (Claude Code headless in a container, started by cron):
  they could write to the database directly. It's kept for later agents that need local access
  (Home Assistant, files), and they can commit to the same repository, so there is still one way
  in.
- **Notion as the inbox:** already connected and good at databases, but the user wanted results
  kept on the home server, next to the portfolio they're about, and linked to its positions.
- **The gainr Journal:** the journal is the user's own thinking; mixing nightly machine output into
  it would bury it. A finding worth keeping can be copied into the journal by hand.
- **YAML front matter:** the more familiar format, but it needs PyYAML, and YAML's implicit typing
  ("NO" becoming false) is a trap for text an agent writes.

## Consequences

- A report shows up within about ten minutes of being pushed, not instantly.
- The server holds a deploy key with write access to the agents repository (for the context
  export), and nothing else on GitHub. The repository holds the portfolio's tickers and weights,
  so it must stay private.
- A bad report file is retried, and logged, on every import until it's fixed or removed; the app
  doesn't show import failures yet.
- briefr has no notification bell yet; the inbox's unread count is the signal for now.

## Addendum (2026-10-19): the holdings' headlines go into the context too

The holdings scan searches the open web for news. That misses what the app already knows: each
position's News card reads Yahoo's headline feed for its symbol (ADR 0030) plus the extra sources
the user set on it (ADR 0026), which is what gives an ETF or a gold tracker any news at all. The
agent can't read those feeds itself: Yahoo answers only some clients, and the cloud environment's
network refuses Yahoo's hosts.

**The server exports the headlines, not the feed addresses.** `scripts/export_briefr_context.py`
now also writes `context/news.md`: for each open holding, once across portfolios, the headlines of
the last 3 days (at most 12) from `fundamentals_service.get_news`, the same merged and cached list
the News card shows, with the time, the title, a summary cut to 300 characters, the link, and
"via <source>" for a story from an extra source. A holding whose feeds fail that night says so
instead of failing the export. Headlines are public, so this adds nothing private to the
repository. The brief tells the agent to start from this file and search beyond it.

Alternatives: handing the agent the feed URLs (it can't fetch them, see above), or adding the
headlines to `holdings.md` (one file mixing the nightly news with the slower-moving holdings list
makes both harder to read, and every news change would look like a holdings change in git).

## What comes next

1. The agents: the holdings scan first, as a cloud scheduled task whose prompt is "read
   `agents/holdings-scan/BRIEF.md` and follow it"; then the app builder, which only picks GitHub
   issues labelled `agent-ok` and only opens pull requests.
2. A morning digest, a check for an agent that missed its run, briefr on the notification bell
   and on taskr's agenda ("act" findings), and a position's own Briefs section in gainr.
3. Push notifications (ntfy) for "act" reports, and event triggers (an earnings date, a new
   transaction).
