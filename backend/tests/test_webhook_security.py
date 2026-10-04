import asyncio
import json

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.api.routes.billing import tara_webhook
from app.api.routes.commerce import commerce_tara_webhook
from app.core.config import settings


def request_with_body(body: bytes) -> Request:
    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    return Request({"type": "http", "method": "POST", "path": "/", "headers": []}, receive)


@pytest.mark.parametrize("handler,product_id", [(tara_webhook, "SAAS-123"), (commerce_tara_webhook, "SCH-123")])
def test_business_id_without_signature_does_not_authenticate_webhook(monkeypatch, handler, product_id) -> None:
    monkeypatch.setattr(settings, "tara_business_id", "business-123")
    monkeypatch.setattr(settings, "tara_webhook_secret", "secret-123")
    body = json.dumps({"productId": product_id, "businessId": "business-123"}).encode()
    with pytest.raises(HTTPException) as exc:
        asyncio.run(handler(request_with_body(body), None))
    assert exc.value.status_code == 422
