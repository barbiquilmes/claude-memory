# /// script
# requires-python = ">=3.10"
# dependencies = ["boto3>=1.34"]
# ///
"""
sync_memory.py: copy memory into one S3-backed store. Every source is already one small .md file
per fact, in the same frontmatter shape (name, description, metadata.type + a body) — this script
only copies, it never reshapes or re-derives anything:

    feedback        ~/.claude/projects/*/memory/*.md (every project) — Claude's own native memory
    events           memory/events/*.md               — written by run_day.py
    investigations   memory/investigations/*.md       — written by run_day.py

    uv run scripts/sync_memory.py --dry-run                 # show what would be uploaded
    uv run scripts/sync_memory.py --bucket my-bucket
    uv run scripts/sync_memory.py                            # bucket from $MEMORY_BUCKET

Needs AWS credentials (standard boto3 chain) and a bucket (--bucket or $MEMORY_BUCKET).
A file is skipped when its content hash matches the last sync (memory/.sync/state.json).
After every run, {prefix}index.json is rewritten to list every object currently in the store.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

GENERATOR = "sync-memory v2"
CLAUDE_DIR = Path(os.environ.get("CLAUDE_CONFIG_DIR", Path.home() / ".claude")).expanduser()
PROJECTS_DIR = CLAUDE_DIR / "projects"
REPO = Path(__file__).resolve().parent.parent
DEFAULT_ROOT = Path(os.environ.get("MEMORY_ROOT", REPO / "memory")).expanduser()
DEFAULT_BUCKET = os.environ.get("MEMORY_BUCKET")
DEFAULT_PREFIX = os.environ.get("MEMORY_PREFIX", "memory/")


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


# ── frontmatter (read-only: just enough to index a file) ───────────────────
def parse_frontmatter(text: str) -> dict:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    meta: dict = {}
    section = meta
    for line in text[4:end].splitlines():
        if not line.strip():
            continue
        if line.startswith("  "):
            k, _, v = line.strip().partition(":")
            section[k.strip()] = v.strip().strip("\"'")
        else:
            k, _, v = line.partition(":")
            v = v.strip().strip("\"'")
            if v:
                meta[k.strip()] = v
            else:
                section = {}
                meta[k.strip()] = section
    return meta


# ── sources: every one is already a native-shaped .md file, copied as-is ───
def iter_native_memory() -> "list[tuple[str, str, str, str, str, str]]":
    """(key, name, text, description, type, project) for every native memory file, every project.

    The S3 key uses each file's own metadata.type (feedback, project, user, reference, ...) —
    whatever Claude's native memory assigned it — not a fixed bucket."""
    out = []
    if not PROJECTS_DIR.is_dir():
        return out
    for project_dir in sorted(PROJECTS_DIR.iterdir()):
        mem_dir = project_dir / "memory"
        if not mem_dir.is_dir():
            continue
        for path in sorted(mem_dir.glob("*.md")):
            if path.name == "MEMORY.md":  # the index, not a memory
                continue
            text = path.read_text()
            meta = parse_frontmatter(text)
            name = meta.get("name", path.stem)
            inner = meta.get("metadata") if isinstance(meta.get("metadata"), dict) else {}
            kind = inner.get("type") or "note"
            key = f"{kind}/{project_dir.name}/{name}.md"
            out.append((key, name, text, meta.get("description", ""), kind, project_dir.name))
    return out


def iter_local(root: Path, kind: str) -> "list[tuple[str, str, str, str, str, str]]":
    """(key, name, text, description, type, project) for every entry run_day.py wrote under memory/<kind>/."""
    out = []
    kind_dir = root / kind
    if not kind_dir.is_dir():
        return out
    for path in sorted(kind_dir.glob("*.md")):
        text = path.read_text()
        meta = parse_frontmatter(text)
        name = meta.get("name", path.stem)
        inner = meta.get("metadata") if isinstance(meta.get("metadata"), dict) else {}
        project = inner.get("project") or "—"
        key = f"{kind}/{project}/{name}.md"
        out.append((key, name, text, meta.get("description", ""), kind, project))
    return out


# ── sync ─────────────────────────────────────────────────────────────────────
def load_state(root: Path) -> dict:
    path = root / ".sync" / "state.json"
    return json.loads(path.read_text()) if path.exists() else {}


def save_state(root: Path, state: dict) -> None:
    path = root / ".sync" / "state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bucket", default=DEFAULT_BUCKET)
    ap.add_argument("--prefix", default=DEFAULT_PREFIX)
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not args.dry_run and not args.bucket:
        print("No bucket (--bucket or $MEMORY_BUCKET); use --dry-run to preview without one.", file=sys.stderr)
        return 1

    items = (iter_native_memory()
             + iter_local(args.root, "events")
             + iter_local(args.root, "investigations"))

    state = load_state(args.root)
    client = None
    if not args.dry_run:
        import boto3
        client = boto3.client("s3")

    uploaded = skipped = 0
    index = []
    for key, name, text, description, kind, project in items:
        digest = sha256(text)
        index.append({"key": args.prefix + key, "name": name, "type": kind,
                       "project": project, "description": description})
        if state.get(key) == digest:
            skipped += 1
            continue
        if args.dry_run:
            print(f"would upload  {key}")
        else:
            client.put_object(Bucket=args.bucket, Key=args.prefix + key,
                               Body=text.encode(), ContentType="text/markdown")
        state[key] = digest
        uploaded += 1

    index_body = json.dumps({"generator": GENERATOR, "count": len(index), "items": index},
                             indent=2, sort_keys=True)
    if args.dry_run:
        print(f"would upload  index.json ({len(index)} items)")
    else:
        client.put_object(Bucket=args.bucket, Key=args.prefix + "index.json",
                           Body=index_body.encode(), ContentType="application/json")
        save_state(args.root, state)

    print(f"\n{uploaded} uploaded, {skipped} unchanged, {len(index)} total.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
