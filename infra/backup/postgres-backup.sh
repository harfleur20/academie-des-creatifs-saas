#!/bin/sh
# Daily dump of the SaaS database, checked before it is kept (same as the mother site's).
# /backups/.last-success feeds the container's health check: no success for 26 h, unhealthy.
set -eu

umask 077
BACKUP_DIR="${BACKUP_DIR:-/backups}"
BACKUP_INTERVAL_SECONDS="${BACKUP_INTERVAL_SECONDS:-86400}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"
DATABASE="${PGDATABASE:-academie_saas}"
BACKUP_B2_ENABLED="${BACKUP_B2_ENABLED:-false}"

mkdir -p "$BACKUP_DIR"

if [ "$BACKUP_B2_ENABLED" != "true" ] && [ "$BACKUP_B2_ENABLED" != "false" ]; then
  echo "BACKUP_B2_ENABLED doit valoir true ou false." >&2
  exit 1
fi

create_backup() {
  timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
  final_path="$BACKUP_DIR/$DATABASE-$timestamp.dump"
  temporary_path="$final_path.tmp"

  rm -f "$temporary_path"
  pg_dump \
    --host="${PGHOST:-saas-db}" \
    --port="${PGPORT:-5432}" \
    --username="${PGUSER:-saas}" \
    --dbname="$DATABASE" \
    --format=custom \
    --compress=6 \
    --no-owner \
    --no-privileges \
    --file="$temporary_path"
  # A dump that pg_restore cannot read is not a backup.
  pg_restore --list "$temporary_path" >/dev/null
  mv "$temporary_path" "$final_path"
  if [ "$BACKUP_B2_ENABLED" = "true" ]; then
    sync-b2-backups "$BACKUP_DIR" "$DATABASE" "$BACKUP_RETENTION_DAYS"
  fi
  date -u +%Y-%m-%dT%H:%M:%SZ > "$BACKUP_DIR/.last-success"
  find "$BACKUP_DIR" -type f -name "$DATABASE-*.dump" -mtime "+$BACKUP_RETENTION_DAYS" -delete
  echo "Sauvegarde PostgreSQL créée : $(basename "$final_path")"
}

while true; do
  create_backup
  if [ "${BACKUP_RUN_ONCE:-false}" = "true" ]; then
    exit 0
  fi
  sleep "$BACKUP_INTERVAL_SECONDS" &
  wait $!
done
