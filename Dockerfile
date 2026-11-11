# Image unique du SaaS : le backend FastAPI sert aussi le frontend compilé, sur chaque domaine
# d'école (ecoles.academiecreatif.com, ecole.academiecreatif.com...). Voir docs/DEPLOIEMENT_COOLIFY.md.

FROM node:22-bookworm-slim AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
# Le frontend appelle l'API sur sa propre origine.
ARG VITE_GOOGLE_CLIENT_ID=""
ENV VITE_API_BASE_URL=/api/v1 \
    VITE_GOOGLE_CLIENT_ID=$VITE_GOOGLE_CLIENT_ID
RUN npm run build


FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FRONTEND_DIST_DIR=/app/frontend_dist
WORKDIR /app/backend
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=frontend /build/frontend/dist /app/frontend_dist
# Fichiers téléversés en stockage local : à monter en volumes persistants dans Coolify.
RUN useradd --system --uid 10001 --home-dir /app --no-create-home saas \
    && mkdir -p uploads private_uploads \
    && chown -R saas:saas uploads private_uploads
USER saas
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"
# Migrations au démarrage, puis l'API. Un processus par défaut, le serveur étant partagé ;
# WEB_CONCURRENCY en ajoute (rien n'est gardé en mémoire entre les requêtes).
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*' --workers ${WEB_CONCURRENCY:-1}"]
