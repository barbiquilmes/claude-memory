# /// script
# requires-python = ">=3.10"
# dependencies = ["anthropic>=0.40"]
# ///
"""
run_day.py: one day of Claude Code logs → six memory outputs.

    uv run scripts/run_day.py                       # today
    uv run scripts/run_day.py --last 30             # first run / backfill: every active day in the last 30
    uv run scripts/run_day.py --day 2026-10-04
    uv run scripts/run_day.py --only events,investigations
    uv run scripts/run_day.py --dry-run             # what would run; no API calls, no writes

Each extractor reads the SAME redacted transcript of the day (not the journal), with its own prompt
and template from assets/:

    journal          memory/journal/YYYY-MM-DD.md     one file per day
    events           memory/events.md                 running log, newest first
    investigations   memory/investigations.md         running log, newest first
    userstyle        memory/userstyle.md              curated rules (US-…), you approve
    nottodo          memory/nottodo.md                curated rules (NT-…), you approve
    mistakes         memory/mistakes.md               curated rules (MS-…), you approve

A day/extractor pair is skipped when its transcript, prompt, template and model are unchanged
(--force to redo). Re-running a day replaces that day's entries and counts, never doubles them.
Before any running file changes, a timestamped copy goes to memory/history/<name>/ and a line is
appended to memory/history/<name>.log. Approved rules are exported to memory/<kind>.claude.md.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import daily_writer as dw  # noqa: E402
import rules_writer as rw  # noqa: E402

GENERATOR = "run-day v1"
REPO = Path(__file__).resolve().parent.parent
DEFAULT_OUT = Path(os.environ.get("MEMORY_ROOT", REPO / "memory")).expanduser()
DEFAULT_ASSETS = REPO / "assets"
DEFAULT_MODEL = os.environ.get("MEMORY_MODEL", "claude-sonnet-5-5")
MAX_OUTPUT_TOKENS = 16_000
EXTRACTORS = ("journal", "events", "investigations", "userstyle", "nottodo", "mistakes")
LOGS = ("events", "investigations")
RULES = ("userstyle", "nottodo", "mistakes")


def now() -> dt.datetime:
    return dt.datetime.now().astimezone()


def short_hash(*parts: str) -> str:
    return hashlib.sha256("\x00".join(parts).encode()).hexdigest()[:16]


# ── generic structured call ─────────────────────────────────────────────────
def record_tool(item_props: dict, required: list[str]) -> dict:
    return {"name": "record", "description": "Record every item found.",
            "input_schema": {"type": "object", "required": ["items"], "properties": {"items": {
                "type": "array", "items": {"type": "object", "properties": item_props, "required": required}}}}}


S = {"type": "string"}
TOOLS = {
    "events": record_tool({"system": S, "what": S, "impact": S, "project": S}, ["system", "what"]),
    "investigations": record_tool({"question": S, "approach": S, "findings": S, "conclusion": S,
                                   "status": {"type": "string", "enum": ["open", "closed"]}, "project": S},
                                  ["question", "status"]),
    "rules": record_tool({"match": {"type": ["string", "null"]}, "rule": S, "instead": S, "why": S,
                          "scope": S, "count": {"type": "integer"}, "explicit": {"type": "boolean"}},
                         ["match", "count", "explicit"]),
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


# ── files with history ──────────────────────────────────────────────────────
def save_with_history(out: Path, path: Path, new_text: str, name: str, note: str) -> bool:
    old = path.read_text() if path.exists() else ""
    strip = lambda t: re.sub(r"updated_at: .*", "", t)  # noqa: E731
    if strip(old) == strip(new_text):
        return False
    stamp = now().strftime("%Y-%m-%dT%H%M%S")
    history = out / "history"
    backup = "-"
    if old:
        (history / name).mkdir(parents=True, exist_ok=True)
        backup, n = f"{name}.{stamp}.md", 1
        while (history / name / backup).exists():  # several changes in the same second
            n += 1
            backup = f"{name}.{stamp}-{n}.md"
        shutil.copy2(path, history / name / backup)
    tmp = path.with_suffix(".md.tmp")
    tmp.write_text(new_text)
    tmp.replace(path)
    history.mkdir(parents=True, exist_ok=True)
    with (history / f"{name}.log").open("a") as log:
        log.write(f"{now().isoformat(timespec='seconds')} {note} backup={backup}\n")
    return True


class LogTemplate:
    """Running-log file (events, investigations): front matter + header + one block per entry."""

    def __init__(self, assets: Path, name: str):
        raw = (assets / "templates" / f"{name}.md").read_text()
        m = re.match(r"^(---\n.*?\n---\n)(.*?)<!-- entry -->\n(.*?)<!-- /entry -->", raw, re.S)
        if not m:
            sys.exit(f"templates/{name}.md needs front matter, a header, and an <!-- entry --> block")
        self.raw, self.front, self.header, self.entry = raw, m.group(1), m.group(2), m.group(3)

    def render(self, by_day: dict[str, list[dict]]) -> str:
        entries = [e for day in sorted(by_day, reverse=True) for e in by_day[day]]
        fm = (self.front.replace("{{updated_at}}", now().isoformat(timespec="seconds"))
              .replace("{{generator}}", GENERATOR).replace("{{entries}}", str(len(entries))))
        out = [fm + self.header.rstrip() + "\n"]
        for e in entries:
            block = re.sub(r"\{\{(\w+)\}\}", lambda m: " ".join(str(e.get(m.group(1)) or "—").split()), self.entry)
            out.append("\n" + block.rstrip() + "\n")
        return "".join(out)


# ── extractors (each returns a result to apply; applying is done sequentially) ─
def run_journal(ctx, day, sessions, transcript):
    jassets = ctx["jassets"]
    projects = sorted({s.project for s in sessions.values()})
    body = dw.summarize(ctx["client"], ctx["model"], jassets.prompt, day, transcript)
    problems = jassets.check_body(body, projects)
    if problems:
        body = dw.summarize(ctx["client"], ctx["model"], jassets.prompt, day, transcript, "; ".join(problems))
        problems = jassets.check_body(body, projects)
    if problems:
        raise ValueError("journal doesn't match the template: " + "; ".join(problems))
    return body


def run_items(ctx, name, day, transcript, tool, existing: str | None = None):
    prompt = (ctx["assets"] / "prompts" / f"{name}.md").read_text()
    user = (f"EXISTING RULES:\n{existing}\n\n" if existing is not None else "") + \
           f"DATE: {day}\n\nTRANSCRIPTS (redacted, trimmed):\n{transcript}"
    return ask_items(ctx["client"], ctx["model"], prompt, user, tool)


def apply_journal(ctx, day, sessions, body, source_hash):
    jassets = ctx["jassets"]
    values = {
        "date": day, "projects": sorted({s.project for s in sessions.values()}), "sessions": len(sessions),
        "session_ids": sorted(sessions), "titles": [s.title for s in sessions.values() if s.title],
        "entrypoints": sorted({s.entrypoint for s in sessions.values()}),
        "user_messages": sum(s.user_msgs for s in sessions.values()),
        "tool_errors": sum(s.tool_errors for s in sessions.values()),
        "interrupts": sum(s.interrupts for s in sessions.values()),
        "claude_minutes": round(sum(s.duration_ms for s in sessions.values()) / 60000),
        "source_hash": source_hash, "generated_at": now().isoformat(timespec="seconds"),
        "generator": GENERATOR, "model": ctx["model"],
    }
    path = ctx["out"] / "journal" / f"{day}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".md.tmp")
    tmp.write_text(jassets.render_front_matter(values) + body + "\n")
    tmp.replace(path)


def apply_log(ctx, name, day, sessions, items):
    store_path = ctx["out"] / f".{name}" / "entries.json"
    store = json.loads(store_path.read_text()) if store_path.exists() else {}
    sids = ", ".join(sorted(s[:8] for s in sessions))
    store[day] = [{**i, "date": day, "sessions": sids} for i in items]
    if not store[day]:
        del store[day]
    store_path.parent.mkdir(parents=True, exist_ok=True)
    store_path.write_text(json.dumps(store, indent=2, ensure_ascii=False))
    text = LogTemplate(ctx["assets"], name).render(store)
    save_with_history(ctx["out"], ctx["out"] / f"{name}.md", text, name, f"day={day} entries={len(items)}")


def load_rules(ctx, kind):
    tpl = rw.Template(ctx["assets"], kind)
    path = ctx["out"] / f"{kind}.md"
    return tpl, tpl.parse(path.read_text() if path.exists() else "", rw.KINDS[kind]["prefix"])


def apply_rules(ctx, kind, day, items):
    cfg = rw.KINDS[kind]
    tpl, rules = load_rules(ctx, kind)
    cand_path = ctx["out"] / f".{kind}" / "candidates.json"
    candidates = json.loads(cand_path.read_text()) if cand_path.exists() else {}
    findings = [{**i, "date": day} for i in items]
    new, updated = rw.merge(rules, candidates, findings, {day}, cfg["prefix"])
    save_with_history(ctx["out"], ctx["out"] / f"{kind}.md", tpl.render(rules), kind,
                      f"day={day} new={','.join(new) or '-'} updated={','.join(updated) or '-'} "
                      f"waiting={len(candidates)}")
    rw.export_approved(rules, ctx["out"] / f"{kind}.claude.md", cfg)
    cand_path.parent.mkdir(parents=True, exist_ok=True)
    cand_path.write_text(json.dumps(candidates, indent=2, ensure_ascii=False))
    return new, updated


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

    jassets = dw.Assets(args.assets)
    days, warnings, _ = dw.load_days(jassets)
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
    for name in only:  # prompt + template + model: a change re-runs that extractor
        parts = [(args.assets / "prompts" / f"{name if name != 'journal' else 'daily'}.md").read_text(),
                 (args.assets / "templates" / f"{name if name != 'journal' else 'daily'}.md").read_text(),
                 args.model]
        fingerprints[name] = short_hash(*parts)

    ctx = {"out": args.out, "assets": args.assets, "model": args.model, "jassets": jassets, "client": None}
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
        transcript = dw.render_day(sessions)
        todo = {}
        for name in only:
            h = short_hash(transcript, fingerprints[name])
            if args.force or state.get(name, {}).get(day) != h:
                todo[name] = h
        if not todo:
            print(f"{day}: all up to date")
            continue
        print(f"{day}: {len(sessions)} session(s), ~{len(transcript) // 4:,} tokens → {', '.join(todo)}")
        if args.dry_run:
            continue

        jobs = {}
        with ThreadPoolExecutor(max_workers=len(todo)) as pool:
            for name in todo:
                if name == "journal":
                    jobs[name] = pool.submit(run_journal, ctx, day, sessions, transcript)
                elif name in LOGS:
                    jobs[name] = pool.submit(run_items, ctx, name, day, transcript, TOOLS[name])
                else:
                    _, rules = load_rules(ctx, name)
                    existing = "\n".join(f"{r['id']} [{r['status']}, {r['scope']}] {r['rule']} — {r['instead']}"
                                         for r in rules) or "(none yet)"
                    jobs[name] = pool.submit(run_items, ctx, name, day, transcript, TOOLS["rules"], existing)

        for name in todo:  # apply sequentially, in a fixed order
            try:
                result = jobs[name].result()
                if name == "journal":
                    apply_journal(ctx, day, sessions, result, todo[name])
                    msg = "written"
                elif name in LOGS:
                    apply_log(ctx, name, day, sessions, result)
                    msg = f"{len(result)} entr{'y' if len(result) == 1 else 'ies'}"
                else:
                    new, updated = apply_rules(ctx, name, day, result)
                    msg = f"new {', '.join(new) or '-'} | updated {', '.join(updated) or '-'}"
                state.setdefault(name, {})[day] = todo[name]
                print(f"   {name:<15} {msg}")
            except Exception as e:  # this extractor is retried next run; the others are kept
                failures += 1
                print(f"   {name:<15} FAILED: {e}", file=sys.stderr)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(state, indent=2))

    if not args.dry_run:  # status edits take effect even when no day changed
        for kind in RULES:
            if kind in only:
                _, rules = load_rules(ctx, kind)
                rw.export_approved(rules, args.out / f"{kind}.claude.md", rw.KINDS[kind])
    print(f"\nDone{'' if not failures else f' with {failures} failure(s)'}.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
