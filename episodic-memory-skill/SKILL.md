---
name: episodic-memory
description: Use when the user explicitly asks to log, save, store, record, remember or note something as an "event" (e.g. "log this event", "record this event") or an "investigation" (e.g. "store this investigation", "save this investigation") — anywhere, in any project. Do NOT use for generic "remember my preference" asks (that's native memory's job) or for anything the user hasn't explicitly flagged.
---

# Episodic memory

Dated, specific-occurrence records — not preferences or profile facts (that's native memory). Write them immediately as one small file; don't wait, don't use native memory for them, and don't ask for confirmation.

## How it works

Each entry type is a template in `assets/templates/<type>.yaml` (currently `event` and `investigation`). The template lists the fields and which ones are `required` — those must be non-empty or the write is refused; everything else is optional and simply left out when not given. `type`, `timestamp` and `sessions` are always written, and the script fills timestamp and session in itself — never pass them.

One script does everything (writes locally, then pushes to S3):

```bash
python3 ~/.claude/skills/episodic-memory/scripts/main.py <type> --<field> "<value>" ...
```

To see the available types and their fields:

```bash
python3 ~/.claude/skills/episodic-memory/scripts/main.py --list
python3 ~/.claude/skills/episodic-memory/scripts/main.py <type> --help
```

A field the template doesn't have can still be recorded with `--set key=value` (repeatable).

## Event

A company-level production change: a model deployed/retrained/turned off, a fraud/chargeback rule or threshold changed, a pipeline broken or fixed, infrastructure changed, a merchant blocked/unblocked. Not an event: anything about a coding session itself (building/testing a skill or script), even if it sounds like a deploy.

```bash
python3 ~/.claude/skills/episodic-memory/scripts/main.py event \
  --system "fraud-model-v3" --what "deployed to production" --impact "scores now reflect v3 thresholds"
```

## Investigation

A fraud-analysis question about a merchant, a segment, or overall traffic: why did a score, a chargeback/approval rate, or a feature go up, down, or change; is this merchant/pattern fraud. Not an investigation: generic debugging with no fraud/traffic question behind it.

```bash
python3 ~/.claude/skills/episodic-memory/scripts/main.py investigation \
  --question "Why did ACME's score drop?" --entity ACME --direction down --status open
```

## Storage

Local: `$MEMORY_ROOT/<template folder>/<type>-<YYYYMMDD-HHMMSS>-<hash>.md` (default `MEMORY_ROOT` is `/tmp/episodic-memory` — the local copy is a staging buffer, not the durable store, since `/tmp` can be cleared; S3 is the durable store).
S3, partitioned by the entry's own timestamp:

```
s3://$S3_BUCKET/bsidoruk/agent_episodic_memory/<template folder>/year=YYYY/month=MM/day=DD/<file>.md
```

`$S3_BUCKET` falls back to `claude-bsidoruk`.

## Download

To pull every entry back down from S3 (e.g. after `/tmp` was cleared, or on another machine), use this script — don't improvise a raw `aws s3 sync` command:

```bash
python3 ~/.claude/skills/episodic-memory/scripts/s3_download.py
```

It syncs into the same local root `main.py` writes to by default (`$MEMORY_ROOT`, or `/tmp/episodic-memory`), so downloaded and locally-written entries end up in one place. Pass `--out <dir>` to land somewhere else instead.

## Rules

- Pass whatever fields you can infer from the conversation; skip the rest. Only ask the user if a `required` field for that type is genuinely missing.
- Run the command with the Bash tool, then tell the user in one short line what was saved and where (the script prints the local path and S3 destination).
- If the S3 upload failed, still report the local save as successful, and say why the push failed.
- If the conversation describes both an event and an investigation, save both as separate calls.
- For "download"/"restore"/"pull memories" requests, use `s3_download.py` — never hand-roll an `aws s3 sync`/`cp` command instead.
