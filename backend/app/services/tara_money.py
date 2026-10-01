from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import unicodedata

import httpx

from app.core.config import settings


SUCCESS_STATUSES = {"paid", "success", "successful", "succeeded", "completed", "confirmed"}
FAILURE_STATUSES = {"failed", "failure", "error", "rejected", "cancelled", "canceled", "expired"}


@dataclass(frozen=True)
class TaraPaymentSession:
    provider_reference: str
    checkout_url: str


@dataclass(frozen=True)
class TaraPaymentVerification:
    status: str
    product_id: str | None = None
    business_id: str | None = None
    amount: int | None = None
    paid_at: datetime | None = None
    transaction_id: str | None = None
    phone_number: str | None = None
    message: str | None = None


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _normalize_status(value: object) -> str:
    status = str(value or "").strip().lower()
    if status in SUCCESS_STATUSES:
        return "paid"
    if status in FAILURE_STATUSES:
        return "failed"
    return "pending"


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value)
    return "".join(char for char in normalized if unicodedata.category(char) != "Mn")


def _parse_nested_payload(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and len(value) <= 16_384:
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _parse_positive_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value > 0:
        return value
    if isinstance(value, str) and value.strip().isdigit():
        parsed = int(value.strip())
        return parsed if parsed > 0 else None
    return None


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    candidate = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(candidate)
    except ValueError:
        return None


def _parse_phone(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    digits = "".join(char for char in value if char.isdigit())
    return digits if 6 <= len(digits) <= 16 else None


def _extract_checkout_url(payload: dict[str, object]) -> str | None:
    data = payload.get("data")
    source = data if isinstance(data, dict) else payload
    for key in (
        "generalLink",
        "genericLink",
        "dikaloLink",
        "cardLink",
        "whatsappLink",
        "telegramLink",
        "smsLink",
    ):
        value = source.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def create_payment_link(
    *,
    product_id: str,
    product_name: str,
    amount_xaf: int,
    description: str,
    return_url: str,
    webhook_url: str,
) -> TaraPaymentSession:
    if not settings.tara_configured:
        raise ValueError("Configuration TaraMoney incomplète.")

    payload = {
        "apiKey": settings.tara_api_key,
        "businessId": settings.tara_business_id,
        "productId": product_id,
        "productName": _normalize_text(product_name),
        "productPrice": amount_xaf,
        "productDescription": _normalize_text(description),
        "productPictureUrl": settings.tara_product_picture_url or None,
        "returnUrl": return_url,
        "webHookUrl": webhook_url,
    }

    try:
        response = httpx.post(
            _join_url(settings.tara_api_base_url, settings.tara_create_payment_path),
            json=payload,
            timeout=settings.tara_timeout_seconds,
        )
    except httpx.TimeoutException as exc:
        raise ValueError("TaraMoney ne répond pas assez vite. Réessayez.") from exc
    except httpx.HTTPError as exc:
        raise ValueError("Impossible de joindre TaraMoney pour le moment.") from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise ValueError("Réponse invalide reçue depuis TaraMoney.") from exc

    checkout_url = _extract_checkout_url(data if isinstance(data, dict) else {})
    status_value = ""
    if isinstance(data, dict):
        nested = data.get("data")
        source = nested if isinstance(nested, dict) else data
        status_value = str(source.get("status") or "").lower()
        message = str(source.get("message") or data.get("message") or "")
    else:
        message = ""

    if response.status_code >= 400 or status_value == "error" or not checkout_url:
        raise ValueError(message or "Création du paiement TaraMoney impossible.")

    return TaraPaymentSession(
        provider_reference=product_id,
        checkout_url=checkout_url,
    )


def verify_payment(product_id: str) -> TaraPaymentVerification:
    if not settings.tara_configured:
        raise ValueError("Configuration TaraMoney incomplète.")

    try:
        response = httpx.post(
            _join_url(settings.tara_api_base_url, settings.tara_verify_payment_path),
            json={
                "apiKey": settings.tara_api_key,
                "businessId": settings.tara_business_id,
                "productId": product_id,
            },
            timeout=settings.tara_timeout_seconds,
        )
    except httpx.TimeoutException as exc:
        raise ValueError("La vérification TaraMoney a dépassé le délai autorisé.") from exc
    except httpx.HTTPError as exc:
        raise ValueError("Impossible de vérifier le paiement auprès de TaraMoney.") from exc

    if response.status_code >= 400:
        raise ValueError(
            f"Vérification TaraMoney refusée (HTTP {response.status_code})."
        )

    try:
        root = response.json()
    except ValueError as exc:
        raise ValueError("Réponse de vérification TaraMoney invalide.") from exc

    if not isinstance(root, dict):
        raise ValueError("Réponse de vérification TaraMoney invalide.")

    data = root.get("data")
    source = data if isinstance(data, dict) else root
    status_value = source.get("status")
    if not status_value:
        raise ValueError("Réponse de vérification TaraMoney sans statut.")

    nested = _parse_nested_payload(source.get("payload"))
    normalized_status = _normalize_status(status_value)

    product_values = [
        value
        for value in (source.get("productId"), nested.get("productId"))
        if isinstance(value, str) and value.strip()
    ]
    if any(value != product_id for value in product_values):
        raise ValueError("Réponse TaraMoney incohérente: productId différent.")
    if normalized_status != "pending" and not product_values:
        raise ValueError("Réponse TaraMoney incohérente: productId absent.")

    business_values = [
        value
        for value in (source.get("businessId"), nested.get("businessId"))
        if isinstance(value, str) and value.strip()
    ]
    if any(value != settings.tara_business_id for value in business_values):
        raise ValueError("Réponse TaraMoney incohérente: businessId différent.")

    nested_status = nested.get("status")
    if isinstance(nested_status, str) and _normalize_status(nested_status) != normalized_status:
        raise ValueError("Réponse TaraMoney incohérente: statuts contradictoires.")

    source_phone = _parse_phone(source.get("phoneNumber"))
    nested_phone = _parse_phone(nested.get("phoneNumber"))
    if source_phone and nested_phone and source_phone != nested_phone:
        raise ValueError("Réponse TaraMoney incohérente: portefeuilles contradictoires.")

    transaction_id = next(
        (
            str(value).strip()
            for value in (
                source.get("transactionId"),
                source.get("paymentId"),
                source.get("collectionId"),
                nested.get("transactionId"),
                nested.get("paymentId"),
                nested.get("collectionId"),
            )
            if value is not None and str(value).strip()
        ),
        None,
    )

    return TaraPaymentVerification(
        status=normalized_status,
        product_id=product_values[0] if product_values else None,
        business_id=business_values[0] if business_values else None,
        amount=_parse_positive_int(nested.get("amount") or source.get("amount")),
        paid_at=_parse_datetime(nested.get("changeDate") or source.get("changeDate")),
        transaction_id=transaction_id,
        phone_number=nested_phone or source_phone,
        message=str(source.get("message") or root.get("message") or "") or None,
    )
