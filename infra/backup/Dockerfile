# The SaaS database's backup container (docker-compose.coolify.yml), built from this folder.
FROM postgres:16-alpine

COPY postgres-backup.sh /usr/local/bin/postgres-backup
COPY restore-postgres.sh /usr/local/bin/restore-postgres
RUN sed -i 's/\r$//' /usr/local/bin/postgres-backup /usr/local/bin/restore-postgres \
    && chmod 0555 /usr/local/bin/postgres-backup /usr/local/bin/restore-postgres

ENTRYPOINT ["/usr/local/bin/postgres-backup"]
