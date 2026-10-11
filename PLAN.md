# Memory pipeline: plan

_Last updated: 2026-10-11_

Turn Claude Code session transcripts into a layered, human-curated memory, starting locally and
ending up in an Agent SDK app on EKS with storage in S3. Built small and incremental.

## Goal

- One small index file is loaded at the start of every session. It links to more detailed memory files.
- Raw transcripts are the source of truth. Memory is a curated, derived view.
- Final target: an app built on the Claude Agent SDK, running on EKS, with all memory stored in S3.

## Decisions so far

| Topic | Decision |
|---|---|
| Starting point | Local only, using personal Claude Code, for now |
| July `eod-memory` skill + `SessionEnd` hook | Delete it (unclear whether it was ever installed) and replace it with this pipeline |
| Exploring logs | Read-only script run locally; output is structure only, safe to share |
| Daily scope | One file per day, all repos together, a section per project |
| Day boundary | Madrid local date from event timestamps; sessions crossing midnight are split by day |
| Summarizer | Anthropic API key, plain `anthropic` Python SDK (Agent SDK only once we build the app) |
| Daily content | Journal first (July template sections); typed memories come in a later iteration |
| Backfill | All history still on disk (up to `cleanupPeriodDays`, default 30) |
| Format | Markdown with YAML front matter (date, projects, sessions), parseable by the future app |
| Review | Dailies are an unreviewed journal; typed memories (later) need human approval |
| Tooling | Python + `uv`, standard library where possible |

## Design principles

1. **Small loaded file.** `INDEX.md` stays around 2–4k tokens. It's paid for in context on every session.
2. **Batch over hooks for learning.** Transcripts already exist, so a scheduled job reads them; hooks
   only for things that must happen live (e.g. offering a review).
3. **No summaries of summaries.** Each rollup is built at most one step from its source.
   Approved facts are never rewritten by a rollup, only linked.
4. **Sliding window for the index.** Finished months contribute their monthly file; the current month
   contributes its weeklies; the current week contributes all dailies since the last weekly.
5. **Episodic vs semantic.** Journals (by time) answer "where was I?". Typed memories (by topic or
   project) answer "what's true?". The index links facts, not weeks.
6. **Memory is data, not instructions.** Never promote memory into rules without human review.
   Treat recalled text as untrusted.
7. **Redact before anything leaves the machine** or is written to disk: card numbers (Luhn-checked),
   emails, AWS keys, tokens, JWTs, private keys, IBANs, plus dLocal-specific patterns.
8. **Fail loudly.** If the transcript format changes or a model call fails, log it, don't advance
   the offset, and retry next run.
9. **Measure it.** Log every review verdict; track kept/reviewed precision.

## Memory types (iteration 5)

```
INVESTIGATION  (one file each, long-lived)
  question · context · data/queries used · findings
  conclusion · confidence · status: open|closed
  date opened/closed · related events · links

EVENT  (one line each, timestamped, append-only)
  when · system/model · what happened · impact · source
  e.g. 2026-10-09 | fraud-model-v3 | turned off | scores fell back to rules

NOTE  (everything else)
  type: preference|correction|decision|fact · text · scope (global|project)
```

- Investigations span sessions: distill proposes "open X" or "add finding to X", not duplicates.
- Events change current state: the index shows a state table derived from the latest event per
  system, so "turned off" gets superseded by "turned back on".
- Notes keep a `type` subfield so the catch-all can be split later.

## Target layout

```
~/.claude/memory/
  INDEX.md                  ← the only @-imported file (from ~/.claude/CLAUDE.md)
  notes.md                  ← approved global notes
  projects/<repo>.md        ← approved project notes
  investigations/<slug>.md  ← one per case
  events.jsonl              ← append-only; drives the state table
  journal/
    2026-10-11.md           ← daily
    2026-W41.md             ← weekly (built from dailies)
    2026-10.md              ← monthly (built from dailies, only after the month ends)
```

`INDEX.md` contains: preferences and corrections inline, current state table, active projects
with links, open investigations, the recent-journal window, and links to everything else.
Detail files are linked as plain paths, **not** `@`-imported (that would load them eagerly).

## Daily file format (iteration 2)

```markdown
---
date: 2026-10-11
projects: [fraud-explain, ds-ai-toolkit]
sessions: 4
source_transcripts: [<session ids>]
generated_at: 2026-10-11T20:00:00+02:00
generator: daily-writer v1
---

## fraud-explain

### Summary
### Decisions & Rationale
### Problems Solved
### Mistakes / Rework / Time-Token Waste
### Learnings
### Open Threads / TODOs
```

## Iterations

| # | Iteration | Output | Status |
|---|---|---|---|
| 1 | **Understand the logs** | `explore_logs.py`: read-only report of schema, event types, day coverage, sizes, token estimate, July-hook leftovers, retention setting | ✅ script ready; waiting for your report |
| 2 | **Daily writer v1** | Transcripts → `journal/YYYY-MM-DD.md` with front matter; backfill all; idempotent re-runs; redaction; Anthropic API | next (today) |
| 3 | Nightly + incremental | 20:00 job (launchd on macOS), per-transcript byte offsets, only new lines, retries | |
| 4 | Rollups + index | Weekly (Sundays) and monthly (month end) from dailies; `INDEX.md` builder; `@` import in `CLAUDE.md` | |
| 5 | Typed memory + review | Investigation/event/note extraction; review queue; first-session-of-day review hook; precision tracking | |
| 6 | Storage interface → S3 | Swap local paths for a storage layer (local FS / S3) | |
| 7 | Agent SDK app on EKS | Transcripts shipped to S3, distill/rollup/index as jobs, memory served to the app | |

Each iteration should work on its own before the next starts.

## Iteration 1: how to run

```bash
python3 explore_logs.py                  # report to stdout
python3 explore_logs.py --json out.json  # also save the raw numbers
```

It reports: session files (top-level vs nested/subagent), event types and their fields, message
content shapes and block types, flags (sidechain, meta, tool errors), Claude Code versions, per-day
sessions/messages/text/approx tokens/projects, sessions spanning midnight, backfill token estimate,
`cleanupPeriodDays`, configured hooks, July hook leftovers and `~/claude-memory/daily`.

## Housekeeping before iteration 2

- [ ] Run `explore_logs.py` and share the report
- [ ] Remove the July `SessionEnd` hook from `~/.claude/settings.json` and delete
      `~/.claude/hooks/session-end-hook.sh` if present
- [ ] Decide what to do with `~/claude-memory/daily/` if it exists (archive or import)
- [ ] Set `"cleanupPeriodDays": 90` in `~/.claude/settings.json` so transcripts outlive missed runs
- [ ] Have an `ANTHROPIC_API_KEY` available locally

## Open questions (later iterations)

- How transcripts reach S3 from the EKS app: Agent SDK session files synced per session, or the app
  writes its own event log?
- Model on EKS: Anthropic API or Bedrock?
- Auto-accept events (factual, timestamped) or review them like notes?
- Multi-user: is memory per user, per team, or both, once it's an app?
- Retention and access control for memory in S3 (it may contain work context).

## Reference

- `mempipe.py` (earlier draft from today): nightly distill → review queue → approved memory, with
  redaction, offsets, schema guard and a first-session review hook. Parts of it will be reused in
  iterations 3 and 5.
- ECC repo (affaan-m/ECC), studied for ideas: layered memory, "memory is unreviewed context",
  create-only entries, hooks for deterministic checks, install-state/doctor/uninstall hygiene.
