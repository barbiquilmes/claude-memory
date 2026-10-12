# claude-memory

Turns Claude Code transcripts (`~/.claude/projects/`) into two memory files, and syncs Claude's own
native memory (preferences, corrections) alongside them. See `PLAN.md` for the longer-term direction
(S3, Agent SDK app on EKS).

## Daily use

```bash
uv run scripts/run_day.py                     # end of the day: process today
uv run scripts/run_day.py --last 30           # first run: every active day in the last 30
uv run scripts/run_day.py --day 2026-10-04    # one specific day
uv run scripts/run_day.py --only events
uv run scripts/run_day.py --dry-run           # show what would run; no API calls, no writes
```

Needs `ANTHROPIC_API_KEY`. Re-running is safe: a day is skipped for each output whose transcript, prompt,
template and model are unchanged (`--force` to redo). If one output fails, the other is kept and only
the failed one is retried next run.

## The two outputs

Both read the same redacted transcript of the day, each with its own prompt and template, and are
running logs, newest first. Re-running a day replaces that day's entries.

| Output | File | What it holds |
|---|---|---|
| Events | `memory/events.md` | Things that happened to systems: deployed, broken, fixed… |
| Investigations | `memory/investigations.md` | Your questions → approach, skills used → findings → conclusion |

Preferences, corrections and mistakes are **not** extracted here — Claude Code's own native memory
(`~/.claude/projects/*/memory/`) already captures those live, for free. `scripts/sync_memory.py` copies
that memory, plus every event and investigation entry, into S3 as one small `.md` file per fact (same
frontmatter shape native memory already uses):

```bash
uv run scripts/sync_memory.py --dry-run
uv run scripts/sync_memory.py --bucket my-bucket     # or $MEMORY_BUCKET
```

## History

Before either running file changes, a copy goes to `memory/history/<name>/<name>.<timestamp>.md`
and a line (day, what changed, backup name) is appended to `memory/history/<name>.log`.

## Where to change things

| You want to… | Edit |
|---|---|
| Change what an output contains | `assets/templates/<name>.md` |
| Change how it's written, or what counts | `assets/prompts/<name>.md` |
| Merge or rename a project | `assets/project_aliases.json` |
| Leave automated sessions out | `JOURNAL_SKIP_ENTRYPOINTS=sdk-cli` |
| Use another model | `MEMORY_MODEL=...` |
| Write somewhere else | `--out PATH` or `MEMORY_ROOT=PATH` |
| Change the S3 destination | `--bucket`/`--prefix` or `$MEMORY_BUCKET`/`$MEMORY_PREFIX` |

Changing a prompt or template makes the next run redo that output for every day you process.

## Other scripts

- `scripts/explore_logs.py`: read-only report of what's in your transcripts.
- `scripts/transcripts.py`: shared transcript loading/redaction/day-splitting used by `run_day.py`.
