#!/usr/bin/env python3
"""Copy verified PostgreSQL dumps to a Backblaze B2 S3-compatible bucket."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import boto3
from boto3.s3.transfer import TransferConfig
from botocore.config import Config
from botocore.exceptions import BotoCoreError


def backup_created_at(name: str, database: str) -> datetime | None:
    if not name.startswith(f"{database}-") or not name.endswith(".dump"):
        return None
    timestamp = name[:-5].rpartition("-")[2]
    try:
        return datetime.strptime(timestamp, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} doit être configuré pour activer les sauvegardes B2.")
    return value


def b2_client():
    endpoint = required_env("BACKUP_B2_ENDPOINT_URL").rstrip("/")
    parsed_endpoint = urlparse(endpoint)
    if parsed_endpoint.scheme != "https" or not parsed_endpoint.netloc:
        raise ValueError("BACKUP_B2_ENDPOINT_URL doit être une URL HTTPS valide.")

    region = required_env("BACKUP_B2_REGION")
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=required_env("BACKUP_B2_ACCESS_KEY_ID"),
        aws_secret_access_key=required_env("BACKUP_B2_SECRET_ACCESS_KEY"),
        region_name=region,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path"},
            retries={"max_attempts": 5, "mode": "standard"},
        ),
    )


def sync_backups(directory: Path, database: str, retention_days: int) -> None:
    if retention_days < 1:
        raise ValueError("BACKUP_RETENTION_DAYS doit être supérieur ou égal à 1.")

    bucket = required_env("BACKUP_B2_BUCKET_NAME")
    prefix = os.environ.get("BACKUP_B2_PREFIX", "academie-saas/postgres").strip("/")
    if not prefix or ".." in prefix.split("/"):
        raise ValueError("BACKUP_B2_PREFIX doit être un préfixe de stockage valide.")

    client = b2_client()
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    key_prefix = f"{prefix}/"
    expected_prefix = f"{key_prefix}{database}-"
    transfer = TransferConfig(
        multipart_threshold=64 * 1024 * 1024,
        multipart_chunksize=64 * 1024 * 1024,
        max_concurrency=2,
        use_threads=True,
    )

    local_backups = sorted(directory.glob(f"{database}-*.dump"))
    if not local_backups:
        raise RuntimeError("Aucune sauvegarde PostgreSQL locale à copier vers B2.")

    paginator = client.get_paginator("list_objects_v2")
    remote_objects: dict[str, dict] = {}
    for page in paginator.paginate(Bucket=bucket, Prefix=expected_prefix):
        for item in page.get("Contents", []):
            key = item.get("Key", "")
            if key.endswith(".dump"):
                remote_objects[key] = item

    for backup_path in local_backups:
        created_at = backup_created_at(backup_path.name, database)
        if created_at is None:
            raise RuntimeError(f"Nom de sauvegarde invalide : {backup_path.name}.")
        if created_at < cutoff:
            continue

        key = f"{key_prefix}{backup_path.name}"
        remote = remote_objects.get(key)
        if remote and remote.get("Size") == backup_path.stat().st_size:
            continue

        client.upload_file(
            str(backup_path),
            bucket,
            key,
            ExtraArgs={"ContentType": "application/octet-stream"},
            Config=transfer,
        )
        uploaded = client.head_object(Bucket=bucket, Key=key)
        if uploaded.get("ContentLength") != backup_path.stat().st_size:
            raise RuntimeError(f"La taille de {backup_path.name} ne correspond pas après copie vers B2.")
        print(f"Copie B2 vérifiée : {key}")

    expired_keys = [
        {"Key": key}
        for key in remote_objects
        if (created_at := backup_created_at(key.rsplit("/", 1)[-1], database)) is not None
        and created_at < cutoff
    ]
    for start in range(0, len(expired_keys), 1000):
        response = client.delete_objects(
            Bucket=bucket,
            Delete={"Objects": expired_keys[start : start + 1000], "Quiet": True},
        )
        errors = response.get("Errors", [])
        if errors:
            raise RuntimeError(f"B2 a refusé la suppression de {len(errors)} sauvegarde(s) expirée(s).")

    print(f"Sauvegardes PostgreSQL synchronisées sur B2 : {bucket}/{prefix}")


def main() -> int:
    if len(sys.argv) != 4:
        print("Usage : sync-b2-backups RÉPERTOIRE BASE RÉTENTION_EN_JOURS", file=sys.stderr)
        return 2

    try:
        sync_backups(Path(sys.argv[1]), sys.argv[2], int(sys.argv[3]))
    except (BotoCoreError, OSError, RuntimeError, ValueError) as exc:
        print(f"Échec de la synchronisation B2 : {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
