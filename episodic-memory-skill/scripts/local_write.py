# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///
"""
local_write.py: write one episodic memory entry as a small .md file, driven by a template.

Templates live in ../assets/templates/<type>.yaml. Each one lists its fields; every field is
optional. Only three things are always written: type, timestamp and session (the last two are
filled in automatically). To add a new kind of entry, drop a new <type>.yaml in that folder —
no code changes needed. The CLI flags are built from the template, so `--help` per type is
always in sync:

    python3 local_write.py --list
    python3 local_write.py event --help
    python3 local_write.py event --system fraud-model-v3 --what "deployed to production"
    python3 local_write.py investigation --question "Why did ACME's score drop?" --status open

Ad-hoc fields not in the template can be added with --set key=value (repeatable); they go in
the frontmatter. Local disk only — pushing to S3 is s3_upload.py's job.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import os
import sys
from pathlib import Path

import yaml

DEFAULT_OUT = Path(os.environ.get("MEMORY_ROOT", "/tmp/episodic-memory")).expanduser()
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "assets" / "templates"
RESERVED = {"type", "timestamp", "sessions"}  # filled in automatically; never settable by the caller


def list_types() -> list[str]:
    return sorted(p.stem for p in TEMPLATES_DIR.glob("*.yaml"))


def load_template(type_: str) -> dict:
    path = TEMPLATES_DIR / f"{type_}.yaml"
    if not path.is_file():
        raise ValueError(f"no template '{type_}'. Available: {', '.join(list_types()) or 'none'}")
    t = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    t.setdefault("folder", type_)
    t["required"] = t.get("required") or []
    t["meta"] = t.get("meta") or {}
    t["body"] = t.get("body") or {}
    t["description"] = t.get("description") or []
    return t


def render(type_: str, template: dict, fields: dict, timestamp: str, session: str) -> tuple[str, str]:
    """Return (file stem, file text). Empty fields are skipped everywhere except `required` ones,
    which must be non-empty — raises ValueError otherwise."""
    vals = {k: str(v).strip() for k, v in fields.items() if v not in (None, "")}

    missing = [f for f in template["required"] if not vals.get(f)]
    if missing:
        raise ValueError(f"{type_} needs {', '.join('--' + m.replace('_', '-') for m in missing)}")

    digest = hashlib.sha256("\x00".join([timestamp, session, *map(str, sorted(vals.items()))]).encode())
    stamp = timestamp[:19].replace("-", "").replace(":", "").replace("T", "-")
    name = f"{type_}-{stamp}-{digest.hexdigest()[:6]}"

    description = " — ".join(vals[k] for k in template["description"] if k in vals)

    meta = {k: v for k, v in vals.items() if k not in template["body"] and k not in RESERVED}
    meta = {"type": type_, "timestamp": timestamp, "sessions": session, **meta}

    front = {"name": name}
    if description:
        front["description"] = description
    front["metadata"] = meta

    sections = [f"**{k.replace('_', ' ').capitalize()}:** {vals[k]}" for k in template["body"] if k in vals]
    text = "---\n" + yaml.safe_dump(front, sort_keys=False, allow_unicode=True, width=1000) + "---\n"
    if sections:
        text += "\n" + "\n\n".join(sections) + "\n"
    return name, text


def save(type_: str, fields: dict, *, out: Path = DEFAULT_OUT, session: str | None = None) -> Path:
    """Write one entry and return its path."""
    template = load_template(type_)
    session = session or os.environ.get("CLAUDE_CODE_SESSION_ID")
    if not session:
        print("warning: no --session and $CLAUDE_CODE_SESSION_ID unset; writing session: unknown", file=sys.stderr)
        session = "unknown"
    timestamp = dt.datetime.now().astimezone().isoformat(timespec="seconds")

    name, text = render(type_, template, fields, timestamp, session)
    out_dir = out / template["folder"]
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}.md"
    path.write_text(text, encoding="utf-8")
    return path


def parse_cli(argv: list[str] | None = None, extra=None) -> tuple[str, dict, argparse.Namespace]:
    """Two-pass parse: read the type, then build flags from its template.
    `extra(parser)` lets a caller (main.py) add its own flags. Returns (type, fields, args)."""
    argv = sys.argv[1:] if argv is None else argv
    if "--list" in argv:
        for t in list_types():
            print(t)
        sys.exit(0)

    first = argparse.ArgumentParser(add_help=False)
    first.add_argument("type", nargs="?")
    known, _ = first.parse_known_args(argv)
    if not known.type or known.type.startswith("-"):
        sys.exit(f"usage: <type> [--field value ...]   types: {', '.join(list_types())}   (--list, <type> --help)")

    try:
        template = load_template(known.type)
    except ValueError as e:
        sys.exit(str(e))

    required_note = f"Required: {', '.join(template['required'])}." if template["required"] else "All fields optional."
    ap = argparse.ArgumentParser(prog=f"{Path(sys.argv[0]).name} {known.type}",
                                 description=f"Write one '{known.type}' entry. {required_note}")
    ap.add_argument("type")
    for name, help_ in {**template["meta"], **template["body"]}.items():
        is_required = name in template["required"]
        ap.add_argument(f"--{name.replace('_', '-')}", dest=name, required=is_required,
                        help=f"{help_}{' (required)' if is_required else ''}")
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                    help="ad-hoc field not in the template (repeatable)")
    ap.add_argument("--session", help="defaults to $CLAUDE_CODE_SESSION_ID")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    if extra:
        extra(ap)
    args = ap.parse_args(argv)

    fields = {n: getattr(args, n) for n in {**template["meta"], **template["body"]}}
    for item in args.set:
        key, sep, value = item.partition("=")
        if not sep or not key.strip():
            sys.exit(f"--set expects KEY=VALUE, got '{item}'")
        key = key.strip().replace("-", "_")
        if key in RESERVED:
            sys.exit(f"--set cannot override '{key}' — it's filled in automatically")
        fields[key] = value
    return known.type, fields, args


def main() -> int:
    type_, fields, args = parse_cli()
    try:
        path = save(type_, fields, out=args.out, session=args.session)
    except ValueError as e:
        sys.exit(str(e))
    print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
