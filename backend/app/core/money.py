"""Amounts as people read them: XAF in whole francs, shown as FCFA."""


def money_label(amount: int, currency: str) -> str:
    """15 000 FCFA for XAF (stored in whole francs); other currencies are stored in cents."""
    code = (currency or "").upper()
    if code == "XAF":
        return f"{amount:,} FCFA".replace(",", " ")
    return f"{amount / 100:,.2f} {code}".replace(",", " ")
