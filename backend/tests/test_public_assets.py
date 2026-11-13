import asyncio
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException, UploadFile
from PIL import Image

from app.core.config import settings
from app.services import assets
from app.services.assets import store_formation_video_asset, store_profile_avatar, store_school_asset


def test_public_brand_assets_reject_svg_and_spoofed_images(monkeypatch):
    monkeypatch.setattr(settings, "storage_provider", "local")
    monkeypatch.setattr(settings, "environment", "development")
    for filename, data in [
        ("logo.svg", b'<svg onload="alert(1)"/>'),
        ("logo.png", b"not a png"),
        ("logo.png", b"\x89PNG\r\n\x1a\n<script>"),
    ]:
        with pytest.raises(HTTPException) as exc:
            asyncio.run(store_school_asset(UploadFile(file=BytesIO(data), filename=filename), 1))
        assert exc.value.status_code == 415


def test_valid_public_image_uses_verified_content_type(monkeypatch):
    monkeypatch.setattr(settings, "storage_provider", "local")
    monkeypatch.setattr(settings, "environment", "development")
    data = BytesIO()
    Image.new("RGB", (2, 2), "red").save(data, format="PNG")
    asset = asyncio.run(store_profile_avatar(UploadFile(file=BytesIO(data.getvalue()), filename="avatar.png", headers={"content-type": "text/html"}), 7))
    path = Path(__file__).resolve().parents[1] / "uploads" / asset["public_url"].split("/uploads/", 1)[1]
    try:
        assert asset["content_type"] == "image/png"
        assert path.read_bytes() == data.getvalue()
    finally:
        path.unlink(missing_ok=True)


def test_formation_video_requires_mp4_and_at_most_three_minutes(monkeypatch):
    mp4 = b"\x00\x00\x00\x18ftypisom"
    monkeypatch.setattr(assets, "MP4", lambda _file: SimpleNamespace(info=SimpleNamespace(length=180.01)))
    with pytest.raises(HTTPException) as exc:
        asyncio.run(store_formation_video_asset(UploadFile(file=BytesIO(mp4), filename="intro.mp4"), 1))
    assert exc.value.status_code == 422

    with pytest.raises(HTTPException) as exc:
        asyncio.run(store_formation_video_asset(UploadFile(file=BytesIO(mp4), filename="intro.mov"), 1))
    assert exc.value.status_code == 415


def test_formation_video_stores_supported_mp4(monkeypatch):
    monkeypatch.setattr(settings, "storage_provider", "local")
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(assets, "MP4", lambda _file: SimpleNamespace(info=SimpleNamespace(length=180.0)))
    asset = asyncio.run(store_formation_video_asset(
        UploadFile(file=BytesIO(b"\x00\x00\x00\x18ftypisom"), filename="intro.mp4"),
        1,
    ))
    path = Path(__file__).resolve().parents[1] / "uploads" / asset["public_url"].split("/uploads/", 1)[1]
    try:
        assert asset["content_type"] == "video/mp4"
        assert asset["duration_seconds"] == 180.0
        assert path.read_bytes() == b"\x00\x00\x00\x18ftypisom"
    finally:
        path.unlink(missing_ok=True)


def test_formation_video_rejects_files_over_50_mib(monkeypatch):
    monkeypatch.setattr(assets, "PRESENTATION_VIDEO_MAX_BYTES", 8)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(store_formation_video_asset(
            UploadFile(file=BytesIO(b"x" * 9), filename="intro.mp4"),
            1,
        ))
    assert exc.value.status_code == 413
