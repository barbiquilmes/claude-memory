# /// script
# requires-python = ">=3.10"
# ///
"""
s3_download.py: pull every episodic memory file down from S3 into the same local root
local_write.py writes to ($MEMORY_ROOT, falling back to /tmp/episodic-memory), so downloaded
and locally-written entries land in one place. Just a thin wrapper over `aws s3 sync` — fine
while there are only a handful of entries; revisit (e.g. an index) if this ever needs to filter
without downloading everything.

    python3 s3_download.py                          # into local_write.py's own default root
    python3 s3_download.py --out /tmp/restored
    python3 s3_download.py --dry-run
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import local_write  # noqa: E402

DEFAULT_BUCKET = "claude-bsidoruk"
PREFIX = "bsidoruk/agent_episodic_memory"
DEFAULT_OUT = local_write.DEFAULT_OUT


def download(out: Path, bucket: str | None = None, dry_run: bool = False) -> Path:
    bucket = bucket or os.environ.get("S3_BUCKET", DEFAULT_BUCKET)
    src = f"s3://{bucket}/{PREFIX}/"
    cmd = ["aws", "s3", "sync", src, str(out)]
    if dry_run:
        cmd.append("--dryrun")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"aws s3 sync exited {result.returncode}")
    sys.stdout.write(result.stdout)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--bucket", default=os.environ.get("S3_BUCKET", DEFAULT_BUCKET))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    try:
        out = download(args.out, bucket=args.bucket, dry_run=args.dry_run)
    except Exception as e:
        sys.exit(str(e))
    print(f"synced to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
