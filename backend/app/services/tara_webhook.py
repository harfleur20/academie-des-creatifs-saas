from __future__ import annotations

import hashlib
import hmac
import re

from app.core.config import settings


SIGNATURE_HEADERS = (
    "x-taramoney-signature",
    "x-signature",
    "taramoney-signature",
)


def _safe_compare(expected: str, received: str) -> bool:
    return hmac.compare_digest(expected.encode("utf-8"), received.encode("utf-8"))


def _secret_header_name() -> str | None:
    value = settings.tara_webhook_secret_header
    if not value or not re.fullmatch(r"[a-z0-9-]+", value):
        return None
    return value


def has_authentication_header(headers: object) -> bool:
    secret_header = _secret_header_name()
    getter = getattr(headers, "get", None)
    if getter is None:
        return False
    if secret_header and getter(secret_header):
        return True
    return any(getter(name) for name in SIGNATURE_HEADERS)


def verify_webhook_authentication(raw_body: bytes, headers: object) -> bool:
    secret = settings.tara_webhook_secret
    if not secret:
        return False

    getter = getattr(headers, "get", None)
    if getter is None:
        return False

    secret_header = _secret_header_name()
    if secret_header:
        received_secret = getter(secret_header)
        if (
            isinstance(received_secret, str)
            and len(received_secret) <= 512
            and _safe_compare(secret, received_secret)
        ):
            return True

    expected = hmac.new(
        secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    for name in SIGNATURE_HEADERS:
        value = getter(name)
        if not isinstance(value, str):
            continue
        received = re.sub(r"^sha256=", "", value.strip(), flags=re.IGNORECASE)
        if re.fullmatch(r"[a-fA-F0-9]{64}", received) and _safe_compare(
            expected,
            received.lower(),
        ):
            return True

    return False
