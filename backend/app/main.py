from pathlib import Path
import posixpath
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response

from app.api.router import api_router
from app.core.config import settings

settings.validate_production_security()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "API multi-écoles de l'Académie des Créatifs SaaS. "
        "Les ressources métier tenant-scoped sont isolées par organisation."
    ),
)

app.include_router(api_router, prefix=settings.api_prefix)

uploads_root = Path(__file__).resolve().parents[1] / "uploads"
uploads_root.mkdir(parents=True, exist_ok=True)


class PublicUploads(StaticFiles):
    async def get_response(self, path: str, scope: dict) -> Response:
        parts = posixpath.normpath('/' + path.replace('\\', '/')).strip('/').split('/')
        if len(parts) >= 4 and parts[0] == "schools" and parts[2] == "assignments":
            return Response(status_code=404)
        response = await super().get_response(path, scope)
        response.headers["X-Content-Type-Options"] = "nosniff"
        if path.lower().endswith(".pdf"):
            response.headers["Content-Disposition"] = "attachment"
        return response


app.mount("/uploads", PublicUploads(directory=uploads_root), name="uploads")


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "academie-des-creatifs-saas",
        "version": settings.app_version,
    }
