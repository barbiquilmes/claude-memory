# /// script
# requires-python = ">=3.10"
# dependencies = ["anthropic>=0.40"]
# ///
"""
daily_writer.py: Claude Code transcripts → one journal file per day.

    uv run scripts/daily_writer.py --dry-run          # no API calls; dumps the redacted model input per day
    uv run scripts/daily_writer.py                    # write/refresh every day still on disk
    uv run scripts/daily_writer.py --day 2026-10-04   # just one day
    uv run scripts/daily_writer.py --force            # rewrite even if sources are unchanged

Format lives in the repo, not in this code:
    assets/templates/daily.md      front matter fields + section headings
    assets/prompts/daily.md        writing rules ({{language}} and {{structure}} are filled in)
    assets/project_aliases.json    folder name → project name

Output: <out>/journal/YYYY-MM-DD.md (default out: <repo>/memory, or $MEMORY_ROOT).
A day is only re-summarized when its transcripts or the template/prompt changed.
Needs ANTHROPIC_API_KEY unless --dry-run.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

GENERATOR = "daily-writer v1.1"
REPO = Path(__file__).resolve().parent.parent
CLAUDE_DIR = Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude")).expanduser()
TRANSCRIPTS = CLAUDE_DIR / "projects"
DEFAULT_OUT = Path(os.environ.get("MEMORY_ROOT", REPO / "memory")).expanduser()
DEFAULT_ASSETS = REPO / "assets"
DEFAULT_MODEL = os.environ.get("MEMORY_MODEL", "claude-sonnet-5-5")
LANGUAGE = os.environ.get("JOURNAL_LANGUAGE", "English")
# comma-separated entrypoints to leave out of the journal (e.g. "sdk-cli" for `claude -p` runs)
SKIP_ENTRYPOINTS = {e.strip() for e in os.environ.get("JOURNAL_SKIP_ENTRYPOINTS", "").split(",") if e.strip()}

MAX_DAY_CHARS = 150_000      # model input budget per day (all sessions)
MAX_TOOL_INPUT = 200         # chars of a tool call's arguments
MAX_TOOL_RESULT = 300        # chars of a tool result
MAX_OUTPUT_TOKENS = 4_000

# ── redaction (backstop, not a classifier) ──────────────────────────────────
def _luhn_ok(d: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(d)):
        n = int(ch)
        if i % 2:
            n = n * 2 - 9 if n * 2 > 9 else n * 2
        total += n
    return total % 10 == 0


PAN_RE = re.compile(r"\b(?:\d[ -]?){12,18}\d\b")
REDACTIONS = [
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S), "[PRIVATE_KEY]"),
    (re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"), "[AWS_KEY_ID]"),
    (re.compile(r"(?i)\b(aws_secret_access_key|aws_session_token|secret|password|passwd|pwd|token|api[_-]?key)\b"
                r"(\s*[:=]\s*)[\"']?[^\s\"',]{8,}"), r"\1\2[REDACTED]"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"), "[API_KEY]"),
    (re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=-]{20,}"), "Bearer [TOKEN]"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"), "[JWT]"),
    (re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "[EMAIL]"),
    (re.compile(r"\b[A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){3,7}\b"), "[IBAN]"),
]
EXTRA_REDACTIONS: list = []  # add dLocal-specific patterns here


def redact(text: str) -> str:
    def pan(m: re.Match) -> str:
        d = re.sub(r"\D", "", m.group())
        return "[PAN]" if 13 <= len(d) <= 19 and _luhn_ok(d) else m.group()

    text = PAN_RE.sub(pan, text)
    for pattern, repl in REDACTIONS + EXTRA_REDACTIONS:
        text = pattern.sub(repl, text)
    return text


# ── assets: template, prompt, aliases ───────────────────────────────────────
class Assets:
    def __init__(self, root: Path):
        template_path = root / "templates" / "daily.md"
        prompt_path = root / "prompts" / "daily.md"
        aliases_path = root / "project_aliases.json"
        for p in (template_path, prompt_path):
            if not p.exists():
                sys.exit(f"Missing asset: {p}")
        raw = template_path.read_text()
        m = re.match(r"^---\n(.*?)\n---\n(.*)$", raw, re.S)
        if not m:
            sys.exit(f"{template_path}: expected '---' front matter followed by a body")
        self.front_matter = m.group(1)
        self.body = m.group(2).strip()
        self.headings = re.findall(r"^### (.+?)\s*$", self.body, re.M)
        if not self.headings or "## {{project}}" not in self.body:
            sys.exit(f"{template_path}: body needs a '## {{{{project}}}}' line and '### ' section headings")
        tv = re.search(r"^template:\s*(.+)$", self.front_matter, re.M)
        self.version = tv.group(1).strip() if tv else "unversioned"
        self.prompt = prompt_path.read_text().replace("{{language}}", LANGUAGE).replace(
            "{{structure}}", self.body.replace("{{project}}", "<project name>"))
        aliases = json.loads(aliases_path.read_text()) if aliases_path.exists() else {}
        self.aliases = {k: v for k, v in aliases.items() if not k.startswith("_")}
        # anything that should trigger a rewrite when it changes
        self.fingerprint = hashlib.sha256((raw + self.prompt + LANGUAGE).encode()).hexdigest()[:8]

    def project(self, raw_name: str) -> str:
        if raw_name in self.aliases:
            return self.aliases[raw_name]
        clean = raw_name.strip().strip("-").strip() or raw_name
        return self.aliases.get(clean, clean)

    def render_front_matter(self, values: dict) -> str:
        def fill(m: re.Match) -> str:
            key = m.group(1)
            if key not in values:
                sys.exit(f"templates/daily.md uses {{{{{key}}}}} but the writer has no value for it. "
                         f"Known: {', '.join(sorted(values))}")
            v = values[key]
            return "[" + ", ".join(json.dumps(x, ensure_ascii=False) for x in v) + "]" if isinstance(v, list) else str(v)

        return "---\n" + re.sub(r"\{\{(\w+)\}\}", fill, self.front_matter) + "\n---\n"

    def check_body(self, body: str, projects: list[str]) -> list[str]:
        """Return a list of problems with the model's output (empty = OK)."""
        problems = []
        blocks = re.split(r"^## (.+?)\s*$", body, flags=re.M)
        found = {blocks[i].strip(): blocks[i + 1] for i in range(1, len(blocks) - 1, 2)}
        for proj in projects:
            if proj not in found:
                problems.append(f"missing project section '## {proj}'")
                continue
            heads = re.findall(r"^### (.+?)\s*$", found[proj], re.M)
            missing = [h for h in self.headings if h not in heads]
            if missing:
                problems.append(f"'{proj}' is missing: {', '.join(missing)}")
        if re.search(r"(?<![\w`'\"])(I|I'm|I've|my|My|we|We)\b(?![`'\"])", body):
            problems.append("first-person voice found (should be 'Claude' / 'the user')")
        return problems


# ── helpers ─────────────────────────────────────────────────────────────────
def clip(text, n: int) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[: n - 1] + "…"


def local_day(ts: str | None) -> str | None:
    if not ts:
        return None
    try:
        return dt.datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone().date().isoformat()
    except ValueError:
        return None


NOISE_PREFIXES = ("<command-name>", "<command-message>", "<command-args>", "<local-command-stdout>",
                  "<local-command-stderr>", "<system-reminder>", "Caveat: The messages below")


def is_noise(text: str) -> bool:
    return text.lstrip().startswith(NOISE_PREFIXES)


# ── transcript → per-day, per-session records ───────────────────────────────
class Session:
    def __init__(self, sid: str, project: str):
        self.sid, self.project = sid, project
        self.title = None
        self.entrypoint = None
        self.lines: list[str] = []
        self.duration_ms = 0
        self.tool_errors = 0
        self.interrupts = 0
        self.denials = 0
        self.user_msgs = 0
        self.skills: set[str] = set()


def load_days(assets: Assets) -> tuple[dict[str, dict[str, Session]], list[str], Counter]:
    """Return {day: {session_id: Session}}, warnings, and a count of sessions per entrypoint."""
    days: dict[str, dict[str, Session]] = defaultdict(dict)
    warnings = []
    entrypoints: Counter = Counter()
    for path in sorted(TRANSCRIPTS.glob("*/*.jsonl")):
        sid = path.stem
        title = cwd = entrypoint = None
        events, bad = [], 0
        with path.open(encoding="utf-8", errors="replace") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    ev = json.loads(line)
                except json.JSONDecodeError:
                    bad += 1
                    continue
                if isinstance(ev, dict):
                    events.append(ev)
        if bad:
            warnings.append(f"{path.parent.name}/{path.name}: {bad} unparseable line(s) skipped")

        for ev in events:  # session-level metadata
            if ev.get("type") == "ai-title" and ev.get("aiTitle"):
                title = ev["aiTitle"]  # keep the latest
            cwd = ev.get("cwd") or cwd
            entrypoint = entrypoint or ev.get("entrypoint")
        entrypoint = entrypoint or "unknown"
        entrypoints[entrypoint] += 1
        if entrypoint in SKIP_ENTRYPOINTS:
            continue

        for ev in events:
            day = local_day(ev.get("timestamp"))
            if not day:
                continue
            t = ev.get("type")
            raw_project = Path(ev.get("cwd") or cwd).name if (ev.get("cwd") or cwd) else path.parent.name
            s = days[day].get(sid)
            if s is None:
                s = days[day][sid] = Session(sid, assets.project(raw_project))
                s.title, s.entrypoint = title, entrypoint

            if t == "system" and isinstance(ev.get("durationMs"), (int, float)):
                s.duration_ms += ev["durationMs"]
                continue
            if t not in ("user", "assistant") or ev.get("isMeta") or ev.get("isSidechain"):
                continue
            if ev.get("interruptedMessageId"):
                s.interrupts += 1
            if ev.get("toolDenialKind"):
                s.denials += 1
            if ev.get("attributionSkill"):
                s.skills.add(str(ev["attributionSkill"]))

            msg = ev.get("message") if isinstance(ev.get("message"), dict) else {}
            content = msg.get("content")
            blocks = [{"type": "text", "text": content}] if isinstance(content, str) else (content or [])
            for b in blocks:
                if not isinstance(b, dict):
                    continue
                bt = b.get("type")
                if bt == "text":
                    text = str(b.get("text", "")).strip()
                    if not text or is_noise(text):
                        continue
                    if t == "user":
                        if text.startswith("[Request interrupted by user"):
                            s.interrupts += 1
                            s.lines.append("USER: [interrupted Claude]")
                            continue
                        s.user_msgs += 1
                        s.lines.append(f"USER: {text}")
                    else:
                        s.lines.append(f"CLAUDE: {text}")
                elif bt == "image" and t == "user":
                    s.lines.append("USER: [pasted an image]")
                elif bt == "tool_use":
                    args = clip(json.dumps(b.get("input", {}), ensure_ascii=False), MAX_TOOL_INPUT)
                    s.lines.append(f"  [tool {b.get('name', '?')}] {args}")
                elif bt == "tool_result":
                    c = b.get("content")
                    if isinstance(c, list):
                        c = " ".join(x.get("text", "") for x in c if isinstance(x, dict))
                    if b.get("is_error"):
                        s.tool_errors += 1
                        s.lines.append(f"  [tool ERROR] {clip(c or '', MAX_TOOL_RESULT)}")
                    else:
                        s.lines.append(f"  [result] {clip(c or '', MAX_TOOL_RESULT)}")
                # thinking blocks are skipped on purpose
    # drop sessions that had nothing human on that day
    for day in list(days):
        days[day] = {k: v for k, v in days[day].items() if v.user_msgs or v.lines}
        if not days[day]:
            del days[day]
    return days, warnings, entrypoints


def fit(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    head = limit // 3
    return text[:head] + "\n[… middle omitted …]\n" + text[-(limit - head):]


def render_day(sessions: dict[str, Session]) -> str:
    by_project: dict[str, list[Session]] = defaultdict(list)
    for s in sessions.values():
        by_project[s.project].append(s)
    per_session_budget = MAX_DAY_CHARS // max(1, len(sessions))
    parts = []
    for proj in sorted(by_project):
        parts.append(f"===== PROJECT: {proj} =====")
        for s in by_project[proj]:
            mins = round(s.duration_ms / 60000)
            parts.append(
                f"--- session {s.sid[:8]} | title: {s.title or '(none)'} | entrypoint: {s.entrypoint} | "
                f"~{mins} min of Claude turns | {s.user_msgs} user msgs | {s.tool_errors} tool errors | "
                f"{s.interrupts} interrupts | {s.denials} denied tool calls | "
                f"skills: {', '.join(sorted(s.skills)) or '-'} ---"
            )
            parts.append(fit("\n".join(s.lines), per_session_budget))
    return redact("\n".join(parts))


# ── model call ──────────────────────────────────────────────────────────────
def summarize(client, model: str, system: str, day: str, transcript: str, feedback: str | None = None) -> str:
    messages = [{"role": "user", "content": f"DATE: {day}\n\nTRANSCRIPTS (redacted, trimmed):\n{transcript}"}]
    if feedback:
        messages[0]["content"] += (f"\n\nA previous attempt had these problems, fix them: {feedback}")
    resp = client.messages.create(model=model, max_tokens=MAX_OUTPUT_TOKENS, system=system, messages=messages)
    return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()


# ── output ──────────────────────────────────────────────────────────────────
def existing_hash(path: Path) -> str | None:
    if not path.exists():
        return None
    m = re.search(r"^source_hash:\s*(\S+)\s*$", path.read_text(), re.M)
    return m.group(1) if m else None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--day", help="only this local date (YYYY-MM-DD)")
    ap.add_argument("--dry-run", action="store_true", help="no API calls; dump model inputs to <out>/.debug/")
    ap.add_argument("--force", action="store_true", help="rewrite even if sources are unchanged")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help=f"memory root (default {DEFAULT_OUT})")
    ap.add_argument("--assets", type=Path, default=DEFAULT_ASSETS, help=f"assets folder (default {DEFAULT_ASSETS})")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    args = ap.parse_args()

    assets = Assets(args.assets)
    if not TRANSCRIPTS.exists():
        print(f"No transcripts at {TRANSCRIPTS}", file=sys.stderr)
        return 1
    days, warnings, entrypoints = load_days(assets)
    for w in warnings:
        print(f"! {w}", file=sys.stderr)
    skipped_ep = f" (skipping: {', '.join(sorted(SKIP_ENTRYPOINTS))})" if SKIP_ENTRYPOINTS else ""
    print(f"Sessions by entrypoint: {dict(entrypoints)}{skipped_ep}")
    print(f"Template: {assets.version} | sections: {len(assets.headings)} | aliases: {len(assets.aliases)}\n")

    targets = [args.day] if args.day else sorted(days)
    journal = args.out / "journal"
    journal.mkdir(parents=True, exist_ok=True)

    client = None
    if not args.dry_run:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print("ANTHROPIC_API_KEY is not set (use --dry-run to test without it).", file=sys.stderr)
            return 1
        import anthropic  # only needed for real runs
        client = anthropic.Anthropic()

    written = skipped = failed = 0
    for day in targets:
        if day not in days:
            print(f"{day}: no sessions")
            continue
        sessions = days[day]
        transcript = render_day(sessions)
        source_hash = hashlib.sha256((transcript + assets.fingerprint).encode()).hexdigest()[:16]
        out_path = journal / f"{day}.md"
        if not args.force and existing_hash(out_path) == source_hash:
            print(f"{day}: unchanged, skipped")
            skipped += 1
            continue
        projects = sorted({s.project for s in sessions.values()})
        if args.dry_run:
            debug = args.out / ".debug"
            debug.mkdir(parents=True, exist_ok=True)
            (debug / f"{day}.input.txt").write_text(transcript)
            (debug / "system_prompt.txt").write_text(assets.prompt)
            print(f"{day}: {len(sessions)} session(s), projects {projects}, {len(transcript):,} chars "
                  f"(~{len(transcript) // 4:,} tokens) → {debug / (day + '.input.txt')}")
            continue
        try:
            body = summarize(client, args.model, assets.prompt, day, transcript)
            problems = assets.check_body(body, projects)
            if problems:  # one retry with the problems spelled out
                body = summarize(client, args.model, assets.prompt, day, transcript, "; ".join(problems))
                problems = assets.check_body(body, projects)
            if problems:
                raise ValueError("output doesn't match the template: " + "; ".join(problems))
        except Exception as e:  # keep going; the day is retried next run
            print(f"{day}: FAILED ({e})", file=sys.stderr)
            failed += 1
            continue
        values = {
            "date": day,
            "projects": projects,
            "sessions": len(sessions),
            "session_ids": sorted(sessions),
            "titles": [s.title for s in sessions.values() if s.title],
            "entrypoints": sorted({s.entrypoint for s in sessions.values()}),
            "user_messages": sum(s.user_msgs for s in sessions.values()),
            "tool_errors": sum(s.tool_errors for s in sessions.values()),
            "interrupts": sum(s.interrupts for s in sessions.values()),
            "claude_minutes": round(sum(s.duration_ms for s in sessions.values()) / 60000),
            "source_hash": source_hash,
            "generated_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
            "generator": GENERATOR,
            "model": args.model,
        }
        tmp = out_path.with_suffix(".md.tmp")
        tmp.write_text(assets.render_front_matter(values) + body + "\n")
        tmp.replace(out_path)
        print(f"{day}: wrote {out_path}")
        written += 1

    if not args.dry_run:
        print(f"\nDone: {written} written, {skipped} unchanged, {failed} failed.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
