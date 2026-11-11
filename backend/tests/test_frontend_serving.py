from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import serve_frontend


def built_frontend(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<div id=root></div>", encoding="utf-8")
    (dist / "assets" / "main-abc123.js").write_text("console.log(1)", encoding="utf-8")
    (dist / "logo.png").write_bytes(b"png")
    (tmp_path / "secret.txt").write_text("hors du build", encoding="utf-8")
    return dist


def client_for(dist: Path) -> TestClient:
    app = FastAPI()

    @app.get("/api/v1/ping")
    def ping() -> dict[str, str]:
        return {"pong": "ok"}

    assert serve_frontend(app, str(dist))
    return TestClient(app)


def test_app_routes_load_the_frontend(tmp_path) -> None:
    client = client_for(built_frontend(tmp_path))
    for path in ("/", "/login", "/app/teacher/live/3"):
        response = client.get(path)
        assert response.status_code == 200
        assert response.text == "<div id=root></div>"
        assert response.headers["cache-control"] == "no-cache"


def test_built_files_are_served_with_long_cache_for_assets(tmp_path) -> None:
    client = client_for(built_frontend(tmp_path))
    asset = client.get("/assets/main-abc123.js")
    assert asset.text == "console.log(1)"
    assert "immutable" in asset.headers["cache-control"]
    assert client.get("/logo.png").content == b"png"
    assert client.head("/assets/main-abc123.js").status_code == 200
    assert client.head("/login").status_code == 200


def test_api_and_uploads_keep_their_own_404(tmp_path) -> None:
    client = client_for(built_frontend(tmp_path))
    assert client.get("/api/v1/ping").json() == {"pong": "ok"}
    assert client.get("/api/v1/missing").status_code == 404
    assert client.get("/uploads/missing.png").status_code == 404


def test_paths_cannot_leave_the_build(tmp_path) -> None:
    client = client_for(built_frontend(tmp_path))
    for path in ("/../secret.txt", "/%2e%2e/secret.txt", "/assets/../../secret.txt"):
        assert "hors du build" not in client.get(path).text


def test_nothing_is_served_without_a_build(tmp_path) -> None:
    assert serve_frontend(FastAPI(), "") is False
    assert serve_frontend(FastAPI(), str(tmp_path / "absent")) is False
