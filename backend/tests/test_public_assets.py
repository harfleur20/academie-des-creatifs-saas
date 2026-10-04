import asyncio
from io import BytesIO
from pathlib import Path

import pytest
from fastapi import HTTPException, UploadFile
from PIL import Image

from app.core.config import settings
from app.services.assets import store_profile_avatar, store_school_asset


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
