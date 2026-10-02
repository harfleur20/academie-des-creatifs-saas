from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.config import settings


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
app.mount("/uploads", StaticFiles(directory=uploads_root), name="uploads")


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "academie-des-creatifs-saas",
        "version": settings.app_version,
    }
