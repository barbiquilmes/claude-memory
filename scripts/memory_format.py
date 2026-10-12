# /// script
# requires-python = ">=3.10"
# ///
"""
memory_format.py: the one place that defines what an event or investigation .md file looks like.
Shared by run_day.py (batch, extracted from transcripts) and memory_save.py (live, called
directly in a session) so both ever produce exactly one shape — the same frontmatter+body
convention Claude Code's own native memory uses (name, description, metadata.type + a body).
"""
from __future__ import annotations

import hashlib


def short_hash(*parts: str) -> str:
    return hashlib.sha256("\x00".join(parts).encode()).hexdigest()[:16]


def render_md(name: str, description: str, meta: dict, body: str) -> str:
    lines = ["---", f"name: {name}", f'description: "{description}"', "metadata:"]
    for k, v in meta.items():
        lines.append(f"  {k}: {v}")
    lines += ["---", "", body.strip(), ""]
    return "\n".join(lines)


def render_event(e: dict) -> tuple[str, str]:
    name = f"event-{short_hash(e['timestamp'][:10], e.get('system', ''), e.get('what', ''))}"
    description = f"{e.get('system', '—')} — {e.get('what', '—')}"
    meta = {"type": "event", "project": e.get("project") or "—", "timestamp": e["timestamp"],
            "sessions": e.get("sessions") or "—"}
    body = e.get("what", "").strip()
    if e.get("impact"):
        body += f"\n\n**Impact:** {e['impact']}"
    return name, render_md(name, description, meta, body)


def render_investigation(i: dict) -> tuple[str, str]:
    name = f"investigation-{short_hash(i['timestamp'][:10], i.get('question', ''))}"
    description = i.get("question", "—")
    meta = {"type": "investigation", "project": i.get("project") or "—", "timestamp": i["timestamp"],
            "entity": i.get("entity") or "—", "metric": i.get("metric") or "—",
            "direction": i.get("direction") or "—", "status": i.get("status", "open"),
            "sessions": i.get("sessions") or "—"}
    body = (f"**Approach:** {i.get('approach') or '—'}\n\n"
            f"**Findings:** {i.get('findings') or '—'}\n\n"
            f"**Conclusion:** {i.get('conclusion') or '—'}")
    return name, render_md(name, description, meta, body)


RENDER = {"events": render_event, "investigations": render_investigation}
