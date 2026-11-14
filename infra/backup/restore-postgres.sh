#!/bin/sh
# Restores one dump over the SaaS database. Stop the app first; see docs/DEPLOIEMENT_COOLIFY.md.
# Usage: CONFIRM_RESTORE=academie_saas restore-postgres /backups/academie_saas-YYYYMMDDTHHMMSSZ.dump
set -eu

DATABASE="${PGDATABASE:-academie_saas}"

if [ "$#" -ne 1 ]; then
  echo "Usage : CONFIRM_RESTORE=$DATABASE $0 /backups/$DATABASE-AAAAMMJJTHHMMSSZ.dump" >&2
  exit 2
fi
if [ "${CONFIRM_RESTORE:-}" != "$DATABASE" ]; then
  echo "Restauration refusée : ajoutez CONFIRM_RESTORE=$DATABASE." >&2
  exit 2
fi
if [ ! -f "$1" ]; then
  echo "Sauvegarde introuvable : $1" >&2
  exit 2
fi

pg_restore --list "$1" >/dev/null
pg_restore \
  --host="${PGHOST:-saas-db}" \
  --port="${PGPORT:-5432}" \
  --username="${PGUSER:-saas}" \
  --dbname="$DATABASE" \
  --clean \
  --if-exists \
  --no-owner \
  --no-privileges \
  --single-transaction \
  --exit-on-error \
  "$1"
echo "Base PostgreSQL restaurée depuis $(basename "$1")."
