# /// script
# requires-python = ">=3.10"
# ///
"""
s3_upload.py: push one already-written episodic memory file to S3. Kept out of
local_write.py on purpose — that script's only job is writing the local .md file; this
one's only job is shipping a copy to S3. Call it after local_write.py, passing the path
it printed.

Partitions by the file's own `timestamp:` frontmatter field (not upload time), so a file written
about an event from an hour ago still lands under that event's own year/month/day:

    s3://<bucket>/bsidoruk/agent_episodic_memory/<template folder>/year=YYYY/month=MM/day=DD/<file>.md

Bucket comes from $S3_BUCKET, falling back to claude-bsidoruk if unset.

    python3 s3_upload.py memory/events/event-<hash>.md
    python3 s3_upload.py memory/investigations/investigation-<hash>.md --dry-run
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_BUCKET = "claude-bsidoruk"
PREFIX = "bsidoruk/agent_episodic_memory"
TIMESTAMP_RE = re.compile(r"^\s*timestamp:\s*['\"]?(\d{4}-\d{2}-\d{2})", re.M)


def read_timestamp(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    m = TIMESTAMP_RE.search(text)
    if not m:
        raise ValueError(f"no timestamp: field found in frontmatter of {path}")
    return m.group(1)


def upload(path: Path, bucket: str | None = None, dry_run: bool = False) -> str:
    """Upload path to S3, return the s3:// destination. Raises ValueError/RuntimeError on failure."""
    if not path.is_file():
        raise ValueError(f"not a file: {path}")

    kind = path.parent.name  # the template's folder, e.g. events / investigations

    bucket = bucket or os.environ.get("S3_BUCKET", DEFAULT_BUCKET)
    timestamp = read_timestamp(path)
    year, month, day = timestamp[0:4], timestamp[5:7], timestamp[8:10]
    key = f"{PREFIX}/{kind}/year={year}/month={month}/day={day}/{path.name}"
    dest = f"s3://{bucket}/{key}"

    cmd = ["aws", "s3", "cp", str(path), dest]
    if dry_run:
        cmd.append("--dryrun")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"aws s3 cp exited {result.returncode}")
    return dest


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", type=Path, help="local .md file written by local_write.py")
    ap.add_argument("--bucket", default=os.environ.get("S3_BUCKET", DEFAULT_BUCKET))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    try:
        dest = upload(args.path, bucket=args.bucket, dry_run=args.dry_run)
    except Exception as e:
        sys.exit(str(e))
    print(f"uploaded to {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
