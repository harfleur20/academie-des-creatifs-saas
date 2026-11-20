from collections.abc import Callable
from contextlib import asynccontextmanager
from pathlib import Path
import posixpath
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from sqlalchemy.orm import Session
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response

from app.api.router import api_router
from app.core.config import settings
from app.db.session import SessionLocal
from app.services.communication_worker import start_communication_worker, stop_communication_worker
from app.services.page_branding import branded_index

settings.validate_production_security()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Queued e-mails leave within the minute (production by default, see communication_worker.py).
    start_communication_worker()
    try:
        yield
    finally:
        stop_communication_worker()


app = FastAPI(
    lifespan=lifespan,
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


def serve_frontend(
    target: FastAPI,
    dist_dir: str,
    session_factory: Callable[[], Session] = SessionLocal,
) -> bool:
    """Serve the built frontend from the API's own origin, on every school domain.

    Its files are served as they are, and index.html answers every other path so the
    app's routes load, with the page's school already in its title, icon and description.
    API and upload paths keep their own 404. Registered last, after every other route.
    """
    dist = Path(dist_dir).resolve() if dist_dir else None
    if dist is None or not (dist / "index.html").is_file():
        return False
    index_document = (dist / "index.html").read_text(encoding="utf-8")
    backend_roots = {settings.api_prefix.strip("/").split("/")[0], "uploads"}

    @target.api_route("/{full_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    def frontend(full_path: str, request: Request) -> Response:
        if full_path.split("/", 1)[0] in backend_roots:
            raise HTTPException(status_code=404, detail="Not Found")
        candidate = (dist / full_path).resolve()
        if full_path and candidate.is_file() and candidate.is_relative_to(dist):
            # Vite fingerprints the files in assets/: they never change under the same name.
            cache = "public, max-age=31536000, immutable" if full_path.startswith("assets/") else "no-cache"
            return FileResponse(candidate, headers={"Cache-Control": cache})
        page = branded_index(
            index_document,
            host=request.url.hostname or "",
            path="/" + full_path,
            query=request.query_params,
            session_factory=session_factory,
        )
        return HTMLResponse(page, headers={"Cache-Control": "no-cache"})

    return True


serve_frontend(app, settings.frontend_dist_dir)
