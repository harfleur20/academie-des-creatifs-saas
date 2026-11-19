"""Move old public assignment submissions into private storage.

Run ``python -m scripts.migrate_legacy_submissions`` from ``backend`` to inspect, then add
``--apply`` to copy, update references, and remove the public objects.
"""
from __future__ import annotations

import argparse
import re
import shutil
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import select

from app.core.config import settings
from app.services.object_storage import b2_client
from app.db.session import SessionLocal
from app.models.entities import AssignmentSubmissionRecord


LEGACY_PATH = re.compile(r"/schools/(?P<org>\d+)/assignments/(?P<filename>[a-f0-9]{32}\.[a-z0-9]+)$")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="move files and update the database")
    args = parser.parse_args()
    if settings.storage_provider == "b2" and (
        not settings.b2_configured
        or not settings.b2_bucket_name
        or not settings.b2_private_bucket_name
        or settings.b2_private_bucket_name == settings.b2_bucket_name
    ):
        parser.error("Set B2_BUCKET_NAME to the legacy source bucket and B2_PRIVATE_BUCKET_NAME to a distinct private target bucket")

    db = SessionLocal()
    try:
        rows = db.scalars(select(AssignmentSubmissionRecord)).all()
        groups: dict[tuple[int, str], list[AssignmentSubmissionRecord]] = defaultdict(list)
        migrated: set[tuple[int, str]] = set()
        for row in rows:
            match = LEGACY_PATH.search(urlsplit(row.file_url).path)
            if match and int(match.group("org")) == row.organization_id:
                groups[(row.organization_id, match.group("filename"))].append(row)
            else:
                private = re.search(r"/assignments/legacy-submissions/([a-f0-9]{32}\.[a-z0-9]+)$", urlsplit(row.file_url).path)
                if private:
                    migrated.add((row.organization_id, private.group(1)))

        print(f"Legacy submission files: {len(groups)}; already migrated references: {len(migrated)}")
        if not args.apply:
            print("Dry run. Add --apply after checking the count and storage configuration.")
            return

        root = Path(__file__).resolve().parents[1]
        client = None
        if settings.storage_provider == "b2":
            from botocore.exceptions import ClientError
            client = b2_client()

        for (org_id, filename), submissions in groups.items():
            key = f"schools/{org_id}/assignments/{filename}"
            if client:
                source = client.head_object(Bucket=settings.b2_bucket_name, Key=key)
                client.copy_object(Bucket=settings.b2_private_bucket_name, Key=key, CopySource={"Bucket": settings.b2_bucket_name, "Key": key})
                target = client.head_object(Bucket=settings.b2_private_bucket_name, Key=key)
                if source["ContentLength"] != target["ContentLength"]:
                    raise RuntimeError(f"Copy size differs for {key}")
            else:
                source_path = root / "uploads" / key
                target_path = root / "private_uploads" / key
                if not source_path.is_file():
                    raise FileNotFoundError(source_path)
                target_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source_path, target_path)
                if source_path.stat().st_size != target_path.stat().st_size:
                    raise RuntimeError(f"Copy size differs for {key}")

            for row in submissions:
                row.file_url = f"{settings.backend_public_url}{settings.api_prefix}/assignments/legacy-submissions/{filename}"
            db.commit()
            if client:
                client.delete_object(Bucket=settings.b2_bucket_name, Key=key)
            else:
                source_path.unlink()
            migrated.add((org_id, filename))
            print(f"Migrated {key}")

        # A previous run may have committed database URLs before public deletion.
        for org_id, filename in sorted(migrated):
            key = f"schools/{org_id}/assignments/{filename}"
            if client:
                try:
                    client.head_object(Bucket=settings.b2_private_bucket_name, Key=key)
                except ClientError as exc:
                    if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey"}:
                        raise RuntimeError(f"Private copy missing for {key}") from exc
                    raise
                client.delete_object(Bucket=settings.b2_bucket_name, Key=key)
            else:
                source_path = root / "uploads" / key
                if (root / "private_uploads" / key).is_file():
                    source_path.unlink(missing_ok=True)
        print("Migration complete. Purge any CDN cache serving the old public URLs.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
