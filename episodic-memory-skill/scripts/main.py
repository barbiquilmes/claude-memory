# /// script
# requires-python = ">=3.10"
# dependencies = ["pyyaml"]
# ///
"""
main.py: single entry point for the episodic-memory skill. Writes the local file, then pushes it
to S3. Same flags as local_write.py (built from assets/templates/<type>.yaml) plus S3 options:

    python3 main.py --list
    python3 main.py event --help
    python3 main.py event --system fraud-model-v3 --what "deployed to production"
    python3 main.py investigation --question "Why did ACME's score drop?" --status open

An S3 failure is non-fatal: the local file is the source of truth, so it still exits 0.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import local_write as save  # noqa: E402
import s3_upload as s3  # noqa: E402


def _s3_flags(ap) -> None:
    ap.add_argument("--bucket", default=os.environ.get("S3_BUCKET", s3.DEFAULT_BUCKET))
    ap.add_argument("--dry-run", action="store_true", help="dry-run the S3 upload only")
    ap.add_argument("--no-upload", action="store_true", help="write locally, skip S3")


def main() -> int:
    type_, fields, args = save.parse_cli(extra=_s3_flags)
    try:
        path = save.save(type_, fields, out=args.out, session=args.session)
    except ValueError as e:
        sys.exit(str(e))
    print(f"wrote {path}")

    if args.no_upload:
        return 0
    try:
        print(f"uploaded to {s3.upload(path, bucket=args.bucket, dry_run=args.dry_run)}")
    except Exception as e:
        print(f"S3 upload failed (local file is saved): {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
