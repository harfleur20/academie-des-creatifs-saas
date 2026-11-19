# The SaaS database's backup container (docker-compose.coolify.yml), built from this folder.
FROM postgres:16-alpine

RUN apk add --no-cache python3 py3-boto3

COPY postgres-backup.sh /usr/local/bin/postgres-backup
COPY restore-postgres.sh /usr/local/bin/restore-postgres
COPY sync-b2-backups.py /usr/local/bin/sync-b2-backups
RUN sed -i 's/\r$//' /usr/local/bin/postgres-backup /usr/local/bin/restore-postgres /usr/local/bin/sync-b2-backups \
    && chmod 0555 /usr/local/bin/postgres-backup /usr/local/bin/restore-postgres /usr/local/bin/sync-b2-backups

ENTRYPOINT ["/usr/local/bin/postgres-backup"]
