# /// script
# requires-python = ">=3.10"
# dependencies = ["anthropic>=0.40"]
# ///
"""
rules_writer.py: daily journals → a curated, human-approved list of rules.

One engine, several kinds (see KINDS below):
    nottodo     mistakes to avoid               → memory/nottodo.md     (NT-001…)
    userstyle   how the user likes to work      → memory/userstyle.md   (US-001…)

    uv run scripts/rules_writer.py --kind userstyle --dry-run
    uv run scripts/rules_writer.py --kind userstyle
    uv run scripts/rules_writer.py --kind nottodo --all     # re-read every daily

How it works
- Reads the configured sections of each new or changed daily (memory/journal/*.md).
- The model maps each finding to an existing rule or proposes a new one. The code owns IDs, evidence
  and counts, so re-reading a day replaces that day's counts instead of adding to them.
- A new rule appears only when seen on 2+ days or when it was explicit (the user corrected Claude or
  stated the preference). Weaker signals wait in memory/.<kind>/candidates.json.
- You own the rule text and the `status` (proposed → approved | retired). Only approved rules are
  exported to memory/<kind>.claude.md, which you can @-import from CLAUDE.md.
- Before every change: a timestamped copy goes to memory/history/<kind>/ and a line is appended to
  memory/history/<kind>.log.
- Format and wording live in assets/templates/<kind>.md and assets/prompts/<kind>.md.
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
from pathlib import Path

GENERATOR = "rules-writer v1"
REPO = Path(__file__).resolve().parent.parent
DEFAULT_OUT = Path(os.environ.get("MEMORY_ROOT", REPO / "memory")).expanduser()
DEFAULT_ASSETS = REPO / "assets"
DEFAULT_MODEL = os.environ.get("MEMORY_MODEL", "claude-sonnet-5-5")
MIN_DAYS = 2                 # days a finding must appear on before it becomes a rule, unless explicit
MAX_BATCH_CHARS = 20_000     # excerpt chars per model call
MAX_OUTPUT_TOKENS = 16_000
STATUSES = {"proposed", "approved", "retired"}

KINDS = {
    "nottodo": {
        "prefix": "NT",
        "sections": ("Mistakes / Rework / Time-Token Waste", "Decisions & Rationale"),
        "export_title": "Not-to-do (approved)",
        "export_line": "{rule}. Instead: {instead}",
    },
    "mistakes": {
        "prefix": "MS",
        "sections": ("Mistakes / Rework / Time-Token Waste",),
        "export_title": "Mistakes to avoid (approved)",
        "export_line": "{rule}. Instead: {instead}",
    },
    "userstyle": {
        "prefix": "US",
        "sections": ("Summary", "Decisions & Rationale", "Mistakes / Rework / Time-Token Waste"),
        "export_title": "How the user likes to work (approved)",
        "export_line": "{rule}. {instead}",
    },
}


def now() -> dt.datetime:
    return dt.datetime.now().astimezone()


# ── template ────────────────────────────────────────────────────────────────
class Template:
    """Renders and parses a rules file. Field labels come from the template, e.g. '- apply: {{instead}}'."""

    def __init__(self, assets: Path, kind: str):
        raw = (assets / "templates" / f"{kind}.md").read_text()
        m = re.match(r"^(---\n.*?\n---\n)(.*?)<!-- entry -->\n(.*?)<!-- /entry -->", raw, re.S)
        if not m:
            sys.exit(f"templates/{kind}.md needs front matter, a header, and an <!-- entry --> block")
        self.front, self.header, self.entry = m.group(1), m.group(2), m.group(3)
        self.labels = dict(re.findall(r"^- ([\w ]+): \{\{(\w+)\}\}", self.entry, re.M))  # label → field
        self.prompt = (assets / "prompts" / f"{kind}.md").read_text()

    def render(self, rules: list[dict]) -> str:
        fm = (self.front.replace("{{updated_at}}", now().isoformat(timespec="seconds"))
              .replace("{{generator}}", GENERATOR).replace("{{rules}}", str(len(rules))))
        out = [fm + self.header.rstrip() + "\n"]
        order = {"approved": 0, "proposed": 1, "retired": 2}
        for r in sorted(rules, key=lambda r: (order[r["status"]], r["id"])):
            ev = r["evidence"]
            values = {**r, "occurrences": sum(ev.values()),
                      "evidence": ", ".join(f"{d} ({n})" if n > 1 else d for d, n in sorted(ev.items()))}
            block = re.sub(r"\{\{(\w+)\}\}", lambda m: str(values.get(m.group(1), "")), self.entry)
            out.append("\n" + block.rstrip() + "\n")
        return "".join(out)

    def parse(self, text: str, prefix: str) -> list[dict]:
        rules = []
        for m in re.finditer(rf"^### ({prefix}-\d+) · (.+?)\n((?:- .*\n?)+)", text, re.M):
            r = {"id": m.group(1), "rule": m.group(2).strip(), "instead": "", "why": "",
                 "scope": "global", "status": "proposed", "evidence": {}}
            for line in m.group(3).splitlines():
                label, _, v = line[2:].partition(":")
                field, v = self.labels.get(label.strip(), label.strip()), v.strip()
                if field == "evidence":
                    for item in filter(None, (x.strip() for x in v.split(","))):
                        d = re.match(r"(\d{4}-\d{2}-\d{2})(?:\s*\((\d+)\))?", item)
                        if d:
                            r["evidence"][d.group(1)] = int(d.group(2) or 1)
                elif field in ("instead", "why", "scope"):
                    r[field] = v
                elif field == "status":
                    r[field] = v if v in STATUSES else "proposed"
            rules.append(r)
        return rules


# ── dailies ─────────────────────────────────────────────────────────────────
def excerpts(daily: Path, sections: tuple[str, ...]) -> str:
    out = []
    for block in re.split(r"^## ", daily.read_text(), flags=re.M)[1:]:
        project = block.splitlines()[0].strip()
        for sec in sections:
            m = re.search(rf"^### {re.escape(sec)}\s*\n(.*?)(?=^### |\Z)", block, re.M | re.S)
            body = m.group(1).strip() if m else ""
            if body and body != "—":
                out.append(f"[{daily.stem} | {project} | {sec}]\n{body}")
    return "\n\n".join(out)


def batches(items: list[tuple[str, str]]) -> list[list[tuple[str, str]]]:
    out, cur, size = [], [], 0
    for day, text in items:
        if cur and size + len(text) > MAX_BATCH_CHARS:
            out.append(cur)
            cur, size = [], 0
        cur.append((day, text))
        size += len(text)
    return out + [cur] if cur else out


# ── model ───────────────────────────────────────────────────────────────────
FINDINGS_TOOL = {
    "name": "record_findings",
    "description": "Record every finding in the excerpts.",
    "input_schema": {
        "type": "object",
        "properties": {"findings": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "match": {"type": ["string", "null"], "description": "existing rule id, or null"},
                "rule": {"type": "string"}, "instead": {"type": "string"}, "why": {"type": "string"},
                "scope": {"type": "string"}, "date": {"type": "string"},
                "count": {"type": "integer"}, "explicit": {"type": "boolean"},
            },
            "required": ["match", "date", "count", "explicit"],
        }}},
        "required": ["findings"],
    },
}


class Truncated(Exception):
    pass


def ask(client, model: str, prompt: str, rules: list[dict], batch: list[tuple[str, str]]) -> list[dict]:
    """One model call; if the answer is cut off, split the batch in half and try each half."""
    existing = "\n".join(f"{r['id']} [{r['status']}, {r['scope']}] {r['rule']} — {r['instead']}"
                         for r in rules) or "(none yet)"
    msg = f"EXISTING RULES:\n{existing}\n\nEXCERPTS:\n" + "\n\n".join(t for _, t in batch)
    try:
        # tool offered but not forced: some models reject a forced tool_choice
        resp = client.messages.create(
            model=model, max_tokens=MAX_OUTPUT_TOKENS, system=prompt, tools=[FINDINGS_TOOL],
            messages=[{"role": "user", "content": msg + "\n\nCall record_findings exactly once with all findings."}])
        if resp.stop_reason == "max_tokens":
            raise Truncated()
        call = next((b for b in resp.content if getattr(b, "type", "") == "tool_use"), None)
        if call is not None:
            return [f for f in call.input.get("findings", []) if isinstance(f, dict)]
        raw = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        raw = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", raw.strip())
        start, end = raw.find("["), raw.rfind("]")
        if start == -1 or end < start:
            raise ValueError(f"model returned neither a tool call nor a JSON array: {raw[:200]}")
        return [f for f in json.loads(raw[start:end + 1]) if isinstance(f, dict)]
    except Truncated:
        if len(batch) == 1:
            raise ValueError(f"output still too long for a single day ({batch[0][0]}); raise MAX_OUTPUT_TOKENS")
        mid = len(batch) // 2
        print(f"  answer cut off for {batch[0][0]}…{batch[-1][0]}; splitting into smaller batches")
        return ask(client, model, prompt, rules, batch[:mid]) + ask(client, model, prompt, rules, batch[mid:])


# ── merge ───────────────────────────────────────────────────────────────────
def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).strip()


def merge(rules: list[dict], candidates: dict, findings: list[dict], days: set[str], prefix: str):
    """Apply findings for `days`. Returns (new rule ids, updated rule ids)."""
    by_id = {r["id"]: r for r in rules}
    for item in list(rules) + list(candidates.values()):  # re-read days replace their old counts
        for d in days:
            item["evidence"].pop(d, None)

    updated = set()
    for f in findings:
        date = str(f.get("date", ""))
        if date not in days:
            continue
        count = max(1, int(f.get("count", 1) or 1))
        match = f.get("match")
        if match not in by_id:  # safety net: the model proposed a rule that already exists
            match = next((r["id"] for r in rules if norm(r["rule"]) == norm(str(f.get("rule", "")))), None)
        if match in by_id:
            ev = by_id[match]["evidence"]
            ev[date] = ev.get(date, 0) + count
            updated.add(match)
            continue
        rule = str(f.get("rule", "")).strip()
        if not rule:
            continue
        c = candidates.setdefault(norm(rule), {
            "rule": rule, "instead": str(f.get("instead", "")).strip(), "why": str(f.get("why", "")).strip(),
            "scope": str(f.get("scope", "global")).strip() or "global", "evidence": {}, "explicit": False})
        c["evidence"][date] = c["evidence"].get(date, 0) + count
        c["explicit"] = c.get("explicit") or c.pop("user_correction", False) or bool(
            f.get("explicit", f.get("user_correction")))

    new = []
    next_n = max([int(r["id"].split("-")[1]) for r in rules] + [0]) + 1
    for key in list(candidates):
        c = candidates[key]
        if not c["evidence"]:
            del candidates[key]
            continue
        if len(c["evidence"]) >= MIN_DAYS or c.get("explicit") or c.get("user_correction"):
            rid = f"{prefix}-{next_n:03d}"
            next_n += 1
            rules.append({"id": rid, "rule": c["rule"], "instead": c["instead"], "why": c["why"],
                          "scope": c["scope"], "status": "proposed", "evidence": c["evidence"]})
            new.append(rid)
            del candidates[key]
    return new, sorted(updated - set(new))


def export_approved(rules: list[dict], path: Path, cfg: dict) -> None:
    approved = [r for r in sorted(rules, key=lambda r: r["id"]) if r["status"] == "approved"]
    lines = [f"# {cfg['export_title']}", "", f"Generated from {path.name.replace('.claude', '')}. Edit there, not here.", ""]
    lines += [f"- {cfg['export_line'].format(**r)}"
              + (f" _(only in {r['scope'][8:]})_" if r["scope"].startswith("project:") else "")
              for r in approved] or ["_(no approved rules yet)_"]
    path.write_text("\n".join(lines) + "\n")


# ── main ────────────────────────────────────────────────────────────────────
def main(default_kind: str | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kind", choices=sorted(KINDS), default=default_kind, required=default_kind is None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--all", action="store_true", help="re-read every daily, not just new or changed ones")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--assets", type=Path, default=DEFAULT_ASSETS)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    args = ap.parse_args()

    kind, cfg = args.kind, KINDS[args.kind]
    tpl = Template(args.assets, kind)
    target = args.out / f"{kind}.md"
    state_dir = args.out / f".{kind}"
    state_file, cand_file = state_dir / "state.json", state_dir / "candidates.json"
    state = json.loads(state_file.read_text()) if state_file.exists() else {"processed": {}}
    candidates = json.loads(cand_file.read_text()) if cand_file.exists() else {}
    old_text = target.read_text() if target.exists() else ""
    rules = tpl.parse(old_text, cfg["prefix"])

    todo = []
    for daily in sorted((args.out / "journal").glob("????-??-??.md")):
        h = hashlib.sha256(daily.read_bytes()).hexdigest()[:16]
        if args.all or state["processed"].get(daily.stem) != h:
            todo.append((daily.stem, excerpts(daily, cfg["sections"]), h))
    if not todo:
        if not args.dry_run:  # still refresh the export, so status edits take effect
            export_approved(rules, args.out / f"{kind}.claude.md", cfg)
        n = sum(r["status"] == "approved" for r in rules)
        print(f"[{kind}] No new or changed dailies. Exported {n} approved rule(s) to {kind}.claude.md")
        return 0
    print(f"[{kind}] Dailies to read: {', '.join(d for d, _, _ in todo)}")
    if args.dry_run:
        print(f"{len(rules)} existing rule(s), {len(candidates)} waiting candidate(s). Nothing written.")
        return 0
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ANTHROPIC_API_KEY is not set.", file=sys.stderr)
        return 1
    import anthropic
    client = anthropic.Anthropic()

    findings = []
    for batch in batches([(d, t) for d, t, _ in todo if t]):
        findings += ask(client, args.model, tpl.prompt, rules, batch)
    days = {d for d, _, _ in todo}
    new, updated = merge(rules, candidates, findings, days, cfg["prefix"])

    new_text = tpl.render(rules)
    changed = re.sub(r"updated_at: .*", "", new_text) != re.sub(r"updated_at: .*", "", old_text)
    if changed:
        stamp = now().strftime("%Y-%m-%dT%H%M%S")
        history = args.out / "history"
        if target.exists():  # timestamped copy BEFORE modifying
            (history / kind).mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, history / kind / f"{kind}.{stamp}.md")
        tmp = target.with_suffix(".md.tmp")
        tmp.write_text(new_text)
        tmp.replace(target)
        history.mkdir(parents=True, exist_ok=True)
        with (history / f"{kind}.log").open("a") as log:
            log.write(f"{now().isoformat(timespec='seconds')} days={','.join(sorted(days))} "
                      f"new={','.join(new) or '-'} updated={','.join(updated) or '-'} "
                      f"waiting={len(candidates)} backup={f'{kind}.{stamp}.md' if old_text else '-'}\n")
    export_approved(rules, args.out / f"{kind}.claude.md", cfg)

    state_dir.mkdir(parents=True, exist_ok=True)
    state["processed"].update({d: h for d, _, h in todo})
    state_file.write_text(json.dumps(state, indent=2))
    cand_file.write_text(json.dumps(candidates, indent=2, ensure_ascii=False))
    print(f"[{kind}] {len(findings)} finding(s) → new: {', '.join(new) or 'none'}; "
          f"updated: {', '.join(updated) or 'none'}; waiting candidates: {len(candidates)}"
          + ("" if changed else f"; {kind}.md unchanged"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
