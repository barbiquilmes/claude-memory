# claude-memory

Turns Claude Code transcripts (`~/.claude/projects/`) into six memory files. See `PLAN.md` for the
longer-term direction (S3, Agent SDK app on EKS).

## Daily use

```bash
uv run scripts/run_day.py                     # end of the day: process today
uv run scripts/run_day.py --last 30           # first run: every active day in the last 30
uv run scripts/run_day.py --day 2026-10-04    # one specific day
uv run scripts/run_day.py --only events,investigations
uv run scripts/run_day.py --dry-run           # show what would run; no API calls, no writes
```

Needs `ANTHROPIC_API_KEY`. Re-running is safe: a day is skipped for each output whose transcript, prompt,
template and model are unchanged (`--force` to redo). If one output fails, the others are kept and only
the failed one is retried next run.

## The six outputs

All six read the same redacted transcript of the day, each with its own prompt and template.

| Output | File | What it holds | You… |
|---|---|---|---|
| Journal | `memory/journal/YYYY-MM-DD.md` | What happened that day, per project | read |
| Events | `memory/events.md` | Things that happened to systems: deployed, broken, fixed… | read |
| Investigations | `memory/investigations.md` | Your questions → approach, skills used → findings → conclusion | read |
| User style | `memory/userstyle.md` | How you like to work (US-001…) | approve |
| Not-to-do | `memory/nottodo.md` | Things you told Claude never to do (NT-001…) | approve |
| Mistakes | `memory/mistakes.md` | Errors Claude made on its own (MS-001…) | approve |

Events and investigations are running logs, newest first. Re-running a day replaces that day's entries.

## Approving rules (user style, not-to-do, mistakes)

1. Open the file and change `- status: proposed` to `approved` (or `retired` to reject; retired rules
   are never proposed again). Reword any rule freely: your text is kept.
2. Run `run_day.py` again. Approved rules are exported to `memory/<kind>.claude.md`.
3. Once, add the exports to `~/.claude/CLAUDE.md`:

```
@/Users/barbi/Documents/github/claude-memory/memory/userstyle.claude.md
@/Users/barbi/Documents/github/claude-memory/memory/nottodo.claude.md
@/Users/barbi/Documents/github/claude-memory/memory/mistakes.claude.md
```

A rule is only proposed after it shows up on 2+ days, or when it was explicit (you stated it or
corrected Claude). Weaker signals wait in `memory/.<kind>/candidates.json`. Counts are per day, so
re-running a day never doubles them.

## History

Before any of the five running files changes, a copy goes to `memory/history/<name>/<name>.<timestamp>.md`
and a line (day, what changed, backup name) is appended to `memory/history/<name>.log`.

## Where to change things

| You want to… | Edit |
|---|---|
| Change what an output contains | `assets/templates/<name>.md` (journal: `daily.md`) |
| Change how it's written, or what counts | `assets/prompts/<name>.md` (journal: `daily.md`) |
| Merge or rename a project | `assets/project_aliases.json` |
| Leave automated sessions out | `JOURNAL_SKIP_ENTRYPOINTS=sdk-cli` |
| Use another model | `MEMORY_MODEL=...` |
| Write somewhere else | `--out PATH` or `MEMORY_ROOT=PATH` |

Changing a prompt or template makes the next run redo that output for every day you process.

## Other scripts

- `scripts/explore_logs.py`: read-only report of what's in your transcripts.
- `scripts/daily_writer.py`: the journal alone (run_day.py uses its code).
- `scripts/rules_writer.py`, `nottodo_writer.py`, `userstyle_writer.py`: the earlier journal-based versions
  of the rules. Superseded by run_day.py, which reads the logs directly.
