#!/usr/bin/env python3
"""
explore_logs.py: read-only structural report of your Claude Code transcripts.

Prints counts, schema shapes, date coverage and sizes. It never prints message
text, file contents or tool outputs, so the report is safe to share.

    python3 explore_logs.py                 # report to stdout
    python3 explore_logs.py --json out.json # also save the raw numbers

Standard library only. Nothing is written except the optional --json file.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

CLAUDE_DIR = Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude")).expanduser()
PROJECTS = CLAUDE_DIR / "projects"


def local_date(ts: str | None) -> str | None:
    if not ts:
        return None
    try:
        return dt.datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone().date().isoformat()
    except ValueError:
        return None


def text_len(content) -> int:
    """Characters a summarizer would see for user/assistant text (not tool output)."""
    if isinstance(content, str):
        return len(content)
    n = 0
    for b in content or []:
        if isinstance(b, dict) and b.get("type") == "text":
            n += len(b.get("text", ""))
    return n


def human(nbytes: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if nbytes < 1024:
            return f"{nbytes:.0f} {unit}"
        nbytes /= 1024
    return f"{nbytes:.1f} TB"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", help="also write the raw numbers to this file")
    args = ap.parse_args()

    if not PROJECTS.exists():
        print(f"No transcript folder at {PROJECTS}")
        return 1

    top_files = sorted(PROJECTS.glob("*/*.jsonl"))
    nested_files = [p for p in PROJECTS.rglob("*.jsonl") if p.parent.parent != PROJECTS]

    event_types = Counter()
    keys_by_type: dict[str, Counter] = defaultdict(Counter)
    content_shape = Counter()            # str vs list, per role
    block_types = Counter()              # text / tool_use / tool_result / thinking / image ...
    flags = Counter()                    # isSidechain, isMeta, is_error ...
    versions = Counter()
    bad_lines = 0
    total_lines = 0
    sessionid_mismatch = 0
    no_timestamp = 0
    tool_names = Counter()

    per_day = defaultdict(lambda: {"sessions": set(), "events": 0, "user_msgs": 0,
                                   "text_chars": 0, "projects": set()})
    session_days: dict[str, set] = defaultdict(set)
    projects_by_folder = {}
    sizes = []

    for path in top_files:
        sizes.append(path.stat().st_size)
        cwd_seen = None
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for line in f:
                if not line.strip():
                    continue
                total_lines += 1
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    bad_lines += 1
                    continue
                if not isinstance(ev, dict):
                    bad_lines += 1
                    continue
                t = ev.get("type", "<missing>")
                event_types[t] += 1
                keys_by_type[t].update(ev.keys())
                if ev.get("version"):
                    versions[ev["version"]] += 1
                for flag in ("isSidechain", "isMeta", "isCompactSummary"):
                    if ev.get(flag):
                        flags[flag] += 1
                if ev.get("sessionId") and ev["sessionId"] != path.stem:
                    sessionid_mismatch += 1
                cwd_seen = ev.get("cwd") or cwd_seen

                day = local_date(ev.get("timestamp"))
                if t in ("user", "assistant"):
                    if not day:
                        no_timestamp += 1
                    msg = ev.get("message") if isinstance(ev.get("message"), dict) else {}
                    content = msg.get("content")
                    content_shape[f"{t}:{'str' if isinstance(content, str) else type(content).__name__}"] += 1
                    if isinstance(content, list):
                        for b in content:
                            if isinstance(b, dict):
                                block_types[f"{t}:{b.get('type')}"] += 1
                                if b.get("type") == "tool_use":
                                    tool_names[b.get("name", "?")] += 1
                                if b.get("is_error"):
                                    flags["tool_result_error"] += 1
                    if day:
                        d = per_day[day]
                        d["sessions"].add(path.stem)
                        d["events"] += 1
                        d["text_chars"] += text_len(content)
                        if cwd_seen:
                            d["projects"].add(Path(cwd_seen).name)
                        is_typed_user = t == "user" and (
                            isinstance(content, str)
                            or any(isinstance(b, dict) and b.get("type") == "text" for b in content or [])
                        )
                        if is_typed_user and not ev.get("isMeta"):
                            d["user_msgs"] += 1
                        session_days[path.stem].add(day)
        projects_by_folder[path.parent.name] = Path(cwd_seen).name if cwd_seen else "?"

    # ── report ─────────────────────────────────────────────────────────────
    out = []
    p = out.append
    days = sorted(per_day)
    p(f"Transcript root: {PROJECTS}")
    p(f"Session files: {len(top_files)} top-level, {len(nested_files)} nested (subagents etc.)")
    p(f"Project folders: {len(projects_by_folder)}")
    if sizes:
        p(f"Size: total {human(sum(sizes))}, median {human(statistics.median(sizes))}, "
          f"largest {human(max(sizes))}")
    p(f"Lines: {total_lines}, unparseable: {bad_lines}")
    if days:
        p(f"Date range (local): {days[0]} → {days[-1]}  ({len(days)} active days)")
    multi = sum(1 for s in session_days.values() if len(s) > 1)
    p(f"Sessions spanning more than one day: {multi}")
    p(f"user/assistant events without a usable timestamp: {no_timestamp}")
    p(f"Events whose sessionId differs from the file name: {sessionid_mismatch}")
    p(f"Claude Code versions seen: {dict(versions.most_common(5))}")

    p("\nEvent types:")
    for k, v in event_types.most_common():
        p(f"  {k:<28} {v}")
    p("\nKeys per event type (key: share of events having it):")
    for t, keys in keys_by_type.items():
        n = event_types[t]
        shown = ", ".join(f"{k}:{c / n:.0%}" for k, c in keys.most_common())
        p(f"  [{t}] {shown}")
    p("\nMessage content shape:")
    for k, v in content_shape.most_common():
        p(f"  {k:<28} {v}")
    p("\nContent block types:")
    for k, v in block_types.most_common():
        p(f"  {k:<28} {v}")
    p(f"\nFlags: {dict(flags)}")
    p(f"Top tools: {dict(tool_names.most_common(12))}")

    p("\nPer day (local): sessions | typed user msgs | text chars | ~tokens | projects")
    total_chars = 0
    for day in days:
        d = per_day[day]
        total_chars += d["text_chars"]
        p(f"  {day}  {len(d['sessions']):>3} | {d['user_msgs']:>4} | {d['text_chars']:>9} | "
          f"{d['text_chars'] // 4:>7} | {', '.join(sorted(d['projects']))}")
    if days:
        p(f"\nBackfill estimate: ~{total_chars // 4:,} input tokens of conversation text "
          f"across {len(days)} days (tool calls/results add more, but get clipped).")

    p("\nProject folders → project name:")
    for folder, name in sorted(projects_by_folder.items()):
        p(f"  {name:<30} ({folder})")

    # ── environment checks ─────────────────────────────────────────────────
    p("\nEnvironment checks:")
    settings_path = CLAUDE_DIR / "settings.json"
    try:
        settings = json.loads(settings_path.read_text())
    except FileNotFoundError:
        settings = {}
    except json.JSONDecodeError:
        settings = {}
        p(f"  ! {settings_path} is not valid JSON")
    p(f"  cleanupPeriodDays: {settings.get('cleanupPeriodDays', 'not set (default 30)')}")
    hooks = settings.get("hooks", {})
    p(f"  hook events configured: {sorted(hooks) or 'none'}")
    hook_blob = json.dumps(hooks)
    p(f"  July session-end-hook referenced in settings.json: {'YES' if 'session-end-hook' in hook_blob else 'no'}")
    for candidate in (CLAUDE_DIR / "hooks" / "session-end-hook.sh",):
        p(f"  {candidate}: {'exists' if candidate.exists() else 'absent'}")
    daily = Path.home() / "claude-memory" / "daily"
    if daily.exists():
        files = sorted(daily.glob("*.md"))
        rng = f"{files[0].stem} → {files[-1].stem}" if files else "empty"
        p(f"  ~/claude-memory/daily: {len(files)} file(s), {rng}")
    else:
        p("  ~/claude-memory/daily: absent")
    p(f"  ANTHROPIC_API_KEY set in this shell: {'yes' if os.environ.get('ANTHROPIC_API_KEY') else 'no'}")

    report = "\n".join(out)
    print(report)

    if args.json:
        Path(args.json).write_text(json.dumps({
            "files": len(top_files), "nested_files": len(nested_files), "lines": total_lines,
            "bad_lines": bad_lines, "event_types": event_types, "content_shape": content_shape,
            "block_types": block_types, "flags": flags, "versions": versions,
            "keys_by_type": {k: dict(v) for k, v in keys_by_type.items()},
            "per_day": {d: {**{k: v for k, v in x.items() if not isinstance(v, set)},
                            "sessions": len(x["sessions"]), "projects": sorted(x["projects"])}
                        for d, x in per_day.items()},
        }, indent=2, default=dict))
        print(f"\nSaved numbers to {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())