# /// script
# requires-python = ">=3.10"
# dependencies = ["anthropic>=0.40"]
# ///
"""
run_day.py: one day of Claude Code logs -> two memory outputs.

    uv run scripts/run_day.py                       # today
    uv run scripts/run_day.py --last 30             # first run / backfill: every active day in the last 30
    uv run scripts/run_day.py --day 2026-10-04
    uv run scripts/run_day.py --only events
    uv run scripts/run_day.py --dry-run             # what would run; no API calls, no writes

Each extractor reads the SAME redacted transcript of the day, with its own prompt from assets/,
and writes one small .md file per entry under memory/<kind>/ — the same frontmatter+body shape
Claude Code's own native memory uses (name, description, metadata.type + a body). Nothing here
invents a different format; sync_memory.py later copies these files as-is, the same way it copies
native memory.

    events           memory/events/YYYY-MM-DD--event-<hash>.md
    investigations   memory/investigations/YYYY-MM-DD--investigation-<hash>.md

Preferences and corrections are not extracted here — those come from Claude Code's own native
memory (~/.claude/projects/*/memory/), synced separately by sync_memory.py.

Nothing is extracted on inference alone: a day/extractor only calls the model if the user
explicitly asked for it in that day's transcript ("log this event", "store this investigation",
or a close variant — see TRIGGERS below). No trigger, no API call, and any previously-written
entries for that day are removed. This is deliberate: letting a model judge "is this a real
company event" over a whole day's transcript produces false positives (it will extract Claude
Code skill-building as if it were a production deploy). Requiring an explicit ask is cheaper and
more reliable than a better prompt.

A day/extractor pair is otherwise skipped when its transcript, prompt and model are unchanged
(--force to redo). Re-running a day deletes and rewrites that day's files for that extractor,
never doubles them. No separate history/backup mechanism: the files live in this git repo, so
`git log -p` is the history.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import transcripts as tx  # noqa: E402
import memory_format as mf  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
DEFAULT_OUT = Path(os.environ.get("MEMORY_ROOT", REPO / "memory")).expanduser()
DEFAULT_ASSETS = REPO / "assets"
DEFAULT_MODEL = os.environ.get("MEMORY_MODEL", "claude-haiku-4-5-20251001")
MAX_OUTPUT_TOKENS = 16_000
EXTRACTORS = ("events", "investigations")

# an extractor only runs on a day if the user explicitly asked for it, e.g. "log this event" /
# "store this investigation" (verb and noun within a short distance, same user message)
VERB = r"(?:log|save|store|record|remember|note)"
USER_LINE = re.compile(r"^USER: (.*)$", re.M)
TRIGGERS = {
    "events": re.compile(rf"\b{VERB}\b[^.\n]{{0,30}}\bevents?\b", re.I),
    "investigations": re.compile(rf"\b{VERB}\b[^.\n]{{0,30}}\binvestigations?\b", re.I),
}


def has_trigger(transcript: str, name: str) -> bool:
    pattern = TRIGGERS[name]
    return any(pattern.search(line) for line in USER_LINE.findall(transcript))


# ── generic structured call ─────────────────────────────────────────────────
def record_tool(item_props: dict, required: list[str]) -> dict:
    return {"name": "record", "description": "Record every item found.",
            "input_schema": {"type": "object", "required": ["items"], "properties": {"items": {
                "type": "array", "items": {"type": "object", "properties": item_props, "required": required}}}}}


S = {"type": "string"}
TOOLS = {
    "events": record_tool({"system": S, "what": S, "impact": S, "project": S}, ["system", "what"]),
    "investigations": record_tool({"question": S, "entity": S, "metric": S, "direction": S, "approach": S,
                                   "findings": S, "conclusion": S,
                                   "status": {"type": "string", "enum": ["open", "closed"]}, "project": S},
                                  ["question", "status"]),
}


def ask_items(client, model: str, system: str, user: str, tool: dict) -> list[dict]:
    """Offer the record tool (not forced: some models reject that); accept a JSON array as fallback."""
    resp = client.messages.create(model=model, max_tokens=MAX_OUTPUT_TOKENS, system=system, tools=[tool],
                                  messages=[{"role": "user", "content": user + "\n\nCall record exactly once."}])
    if resp.stop_reason == "max_tokens":
        raise ValueError("answer cut off (raise MAX_OUTPUT_TOKENS)")
    call = next((b for b in resp.content if getattr(b, "type", "") == "tool_use"), None)
    if call is not None:
        return [i for i in call.input.get("items", []) if isinstance(i, dict)]
    raw = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    raw = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", raw.strip())
    start, end = raw.find("["), raw.rfind("]")
    if start == -1 or end < start:
        raise ValueError(f"model returned neither a tool call nor a JSON array: {raw[:200]}")
    return [i for i in json.loads(raw[start:end + 1]) if isinstance(i, dict)]


# ── extractor ─────────────────────────────────────────────────────────────
def run_items(ctx, name, day, transcript) -> list[dict]:
    prompt = (ctx["assets"] / "prompts" / f"{name}.md").read_text()
    user = f"DATE: {day}\n\nTRANSCRIPTS (redacted, trimmed):\n{transcript}"
    return ask_items(ctx["client"], ctx["model"], prompt, user, TOOLS[name])


def apply_entries(ctx, name, day, sessions, items):
    out_dir = ctx["out"] / name
    out_dir.mkdir(parents=True, exist_ok=True)
    for p in out_dir.glob(f"{day}--*.md"):  # re-running a day replaces its files, never doubles them
        p.unlink()
    sids = ", ".join(sorted(sessions))
    for i in items:
        entry = {**i, "timestamp": day, "sessions": sids}
        fname, text = mf.RENDER[name](entry)
        (out_dir / f"{day}--{fname}.md").write_text(text)


# ── main ────────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--day", help="one local date (YYYY-MM-DD); default today")
    g.add_argument("--last", type=int, metavar="N", help="every active day in the last N days")
    ap.add_argument("--only", help=f"comma-separated subset of: {', '.join(EXTRACTORS)}")
    ap.add_argument("--force", action="store_true", help="redo even if nothing changed")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--assets", type=Path, default=DEFAULT_ASSETS)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    args = ap.parse_args()

    only = [x.strip() for x in args.only.split(",")] if args.only else list(EXTRACTORS)
    bad = [x for x in only if x not in EXTRACTORS]
    if bad:
        sys.exit(f"unknown extractor(s): {', '.join(bad)}")

    aliases = tx.Aliases(args.assets)
    days, warnings, _ = tx.load_days(aliases)
    for w in warnings:
        print(f"! {w}", file=sys.stderr)
    today = dt.date.today()
    if args.last:
        first = (today - dt.timedelta(days=args.last - 1)).isoformat()
        targets = [d for d in sorted(days) if d >= first]
    else:
        targets = [args.day or today.isoformat()]

    state_path = args.out / ".run" / "state.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    fingerprints = {}
    for name in only:  # prompt + model: a change re-runs that extractor
        parts = [(args.assets / "prompts" / f"{name}.md").read_text(), args.model]
        fingerprints[name] = mf.short_hash(*parts)

    ctx = {"out": args.out, "assets": args.assets, "model": args.model, "client": None}
    if not args.dry_run:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("ANTHROPIC_API_KEY is not set (use --dry-run to test without it).", file=sys.stderr)
            return 1
        import anthropic
        ctx["client"] = anthropic.Anthropic()

    failures = 0
    for day in targets:
        if day not in days:
            print(f"{day}: no sessions")
            continue
        sessions = days[day]
        transcript = tx.render_day(sessions)
        todo, untriggered = {}, []
        for name in only:
            if not has_trigger(transcript, name):
                state.get(name, {}).pop(day, None)
                untriggered.append(name)
                continue
            h = mf.short_hash(transcript, fingerprints[name])
            if args.force or state.get(name, {}).get(day) != h:
                todo[name] = h
        if args.dry_run:
            if todo:
                print(f"{day}: {len(sessions)} session(s), ~{len(transcript) // 4:,} tokens → {', '.join(todo)}")
            elif untriggered:
                print(f"{day}: no trigger for {', '.join(untriggered)}")
            else:
                print(f"{day}: all up to date")
            continue

        for name in untriggered:  # no explicit ask: clear any stale entries, no API call
            apply_entries(ctx, name, day, sessions, [])

        if todo:
            print(f"{day}: {len(sessions)} session(s), ~{len(transcript) // 4:,} tokens → {', '.join(todo)}")
            jobs = {}
            with ThreadPoolExecutor(max_workers=len(todo)) as pool:
                for name in todo:
                    jobs[name] = pool.submit(run_items, ctx, name, day, transcript)

            for name in todo:  # apply sequentially, in a fixed order
                try:
                    result = jobs[name].result()
                    apply_entries(ctx, name, day, sessions, result)
                    msg = f"{len(result)} entr{'y' if len(result) == 1 else 'ies'}"
                    state.setdefault(name, {})[day] = todo[name]
                    print(f"   {name:<15} {msg}")
                except Exception as e:  # this extractor is retried next run; the others are kept
                    failures += 1
                    print(f"   {name:<15} FAILED: {e}", file=sys.stderr)
        elif untriggered:
            print(f"{day}: no trigger for {', '.join(untriggered)}")

        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(state, indent=2))

    print(f"\nDone{'' if not failures else f' with {failures} failure(s)'}.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
