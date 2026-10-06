from __future__ import annotations

import re

import phonenumbers
from phonenumbers import PhoneNumberFormat


# WhatsApp accounts can remain attached to older national numbering plans long after
# telecom operators have migrated to a newer plan. We preserve a small set of
# historical African national-number lengths instead of guessing a new number.
# A future WhatsApp verification step remains the source of truth for reachability.
LEGACY_WHATSAPP_NSN_LENGTHS: dict[str, set[int]] = {
    "BJ": {8},   # Benin: historical 8-digit plan
    "CI": {8},   # Côte d'Ivoire: historical 8-digit plan
    "CM": {8},   # Cameroon: historical 8-digit plan
    "GA": {7},   # Gabon: historical 7-digit plan
}


def supported_phone_countries() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for region in sorted(phonenumbers.SUPPORTED_REGIONS):
        calling_code = phonenumbers.country_code_for_region(region)
        if not calling_code:
            continue
        rows.append({"code": region, "dial_code": f"+{calling_code}"})
    return rows


def normalize_whatsapp_phone(value: str, country: str) -> tuple[str, bool]:
    region = (country or "").strip().upper()
    if region not in phonenumbers.SUPPORTED_REGIONS:
        raise ValueError("Pays non pris en charge pour le numéro WhatsApp.")

    raw = (value or "").strip()
    if not raw:
        raise ValueError("Renseignez votre numéro WhatsApp.")

    try:
        parsed = phonenumbers.parse(raw, region)
    except phonenumbers.NumberParseException as exc:
        raise ValueError("Numéro WhatsApp invalide pour le pays sélectionné.") from exc

    if phonenumbers.is_valid_number(parsed):
        return phonenumbers.format_number(parsed, PhoneNumberFormat.E164), False

    # Compatibility path for WhatsApp accounts that can still use a historical
    # national number. We only accept digits with a known historical length and
    # preserve them exactly under the country's calling code; we never invent a
    # migration prefix.
    digits = re.sub(r"\D", "", raw)
    country_code = str(phonenumbers.country_code_for_region(region))
    if raw.startswith("+") and digits.startswith(country_code):
        national_digits = digits[len(country_code):]
    else:
        national_digits = digits.lstrip("0")

    allowed_lengths = LEGACY_WHATSAPP_NSN_LENGTHS.get(region, set())
    if len(national_digits) in allowed_lengths and national_digits:
        return f"+{country_code}{national_digits}", True

    raise ValueError("Numéro WhatsApp invalide pour le pays sélectionné.")
