# /// script
# requires-python = ">=3.10"
# ///
"""
transcripts.py: shared code to turn Claude Code transcripts (~/.claude/projects/) into
per-day, per-session records. Used by run_day.py for every extractor (events, investigations).

    load_days()   -> {day: {session_id: Session}}, reading every *.jsonl under ~/.claude/projects
    render_day()  -> one redacted text block per day, ready to hand to a model
    redact()      -> PII/secrets backstop (card numbers, keys, tokens, emails, IBANs)
    Aliases       -> folder name -> project name, from assets/project_aliases.json
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path

CLAUDE_DIR = Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude")).expanduser()
TRANSCRIPTS = CLAUDE_DIR / "projects"
# comma-separated entrypoints to leave out (e.g. "sdk-cli" for `claude -p` runs)
SKIP_ENTRYPOINTS = {e.strip() for e in os.environ.get("JOURNAL_SKIP_ENTRYPOINTS", "").split(",") if e.strip()}

MAX_DAY_CHARS = 150_000      # model input budget per day (all sessions)
MAX_TOOL_INPUT = 200         # chars of a tool call's arguments
MAX_TOOL_RESULT = 300        # chars of a tool result


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


# ── project aliases ──────────────────────────────────────────────────────────
class Aliases:
    def __init__(self, assets_root: Path):
        path = assets_root / "project_aliases.json"
        raw = json.loads(path.read_text()) if path.exists() else {}
        self.map = {k: v for k, v in raw.items() if not k.startswith("_")}

    def project(self, raw_name: str) -> str:
        if raw_name in self.map:
            return self.map[raw_name]
        clean = raw_name.strip().strip("-").strip() or raw_name
        return self.map.get(clean, clean)


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


def load_days(aliases: Aliases) -> tuple[dict[str, dict[str, Session]], list[str], Counter]:
    """Return {day: {session_id: Session}}, warnings, and a count of sessions per entrypoint."""
    days: dict[str, dict[str, Session]] = defaultdict(dict)
    warnings = []
    entrypoints: Counter = Counter()
    if not TRANSCRIPTS.exists():
        return days, warnings, entrypoints
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
                s = days[day][sid] = Session(sid, aliases.project(raw_project))
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
