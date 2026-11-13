"""Payment plans for a formation: when each payment of an instalment plan is due.

Each school chooses whether a formation can be paid in instalments and how many
payments at most. The price and the time left then set what is really offered:

- under 70 000 FCFA, a single payment; above, each payment is at least 35 000 FCFA;
- for a session, payments are at least a week apart and the last one falls five
  days before the session ends: a one-month session can be paid in 3 times within
  the month;
- an online formation, without an end, is paid a month apart.

This replaces the mother site's rule (1, 2 or 3 payments from the session's length
alone): the school can sell an expensive short session in several payments.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

INSTALLMENT_FINAL_MARGIN_DAYS = 5
INSTALLMENT_MIN_INTERVAL_DAYS = 7
ONLINE_INSTALLMENT_INTERVAL_DAYS = 30
# Only XAF amounts are stored in whole francs (other currencies are in cents), so only
# they are rounded to 500 FCFA like on the mother site, and only they follow the price rule.
FCFA_CURRENCIES = frozenset({"XAF"})
FCFA_ROUNDING = 500
INSTALLMENT_MIN_TOTAL_FCFA = 70_000
INSTALLMENT_MIN_PAYMENT_FCFA = 35_000


def price_installment_limit(total: int, currency: str) -> int:
    """How many payments the price allows: one under 70 000 FCFA, then 35 000 FCFA at least each."""
    if total <= 0:
        return 1
    if currency.upper() not in FCFA_CURRENCIES:
        return total  # no price rule outside FCFA: the school's count and the dates decide
    if total < INSTALLMENT_MIN_TOTAL_FCFA:
        return 1
    return total // INSTALLMENT_MIN_PAYMENT_FCFA


def installment_due_dates(*, session_end: date, today: date, max_count: int) -> list[date]:
    """Due dates of each payment, the first one today, spread evenly up to five days before the end."""
    deadline = session_end - timedelta(days=INSTALLMENT_FINAL_MARGIN_DAYS)
    available = (deadline - today).days
    count = min(max_count, 1 + max(0, available) // INSTALLMENT_MIN_INTERVAL_DAYS)
    if count <= 1:
        return [today]
    return [today + timedelta(days=available * index // (count - 1)) for index in range(count)]


def session_installment_dates(
    *,
    allow_installments: bool,
    school_max_count: int,
    session_end: date,
    total: int,
    currency: str,
    today: date,
) -> list[date]:
    """The plan offered when the student pays a session in instalments; a single date means none."""
    if not allow_installments or school_max_count < 2:
        return [today]
    limit = min(school_max_count, price_installment_limit(total, currency))
    return installment_due_dates(session_end=session_end, today=today, max_count=limit)


def online_installment_dates(
    *,
    allow_installments: bool,
    school_max_count: int,
    total: int,
    currency: str,
    today: date,
) -> list[date]:
    """The plan of an online formation, which has no end: a payment a month."""
    if not allow_installments or school_max_count < 2:
        return [today]
    count = min(school_max_count, price_installment_limit(total, currency))
    return [today + timedelta(days=ONLINE_INSTALLMENT_INTERVAL_DAYS * index) for index in range(max(1, count))]


RESERVATION_DEPOSIT_DUE_DAYS = 10


def _unit(currency: str) -> int:
    return FCFA_ROUNDING if currency.upper() in FCFA_CURRENCIES else 1


def reservation_deposit_available(
    *,
    format_type: str,
    enabled: bool,
    total: int,
    currency: str,
    session_start: date,
    today: date,
) -> bool:
    """A live session can be reserved with a deposit while it starts in more than ten days."""
    return (
        format_type == "live"
        and enabled
        and total >= 2 * _unit(currency)
        and (session_start - today).days > RESERVATION_DEPOSIT_DUE_DAYS
    )


def reservation_deposit_amount(total: int, percent: float, currency: str) -> int:
    """The percentage of the price, rounded to 500 FCFA, never the whole price."""
    unit = _unit(currency)
    if total <= 0:
        return 0
    rounded = int(Decimal(total) * Decimal(str(percent)) / Decimal(100 * unit) + Decimal("0.5")) * unit
    maximum = ((total - 1) // unit) * unit
    return min(max(rounded, unit), maximum)


def reservation_balance_due_date(session_start: date) -> date:
    return session_start - timedelta(days=RESERVATION_DEPOSIT_DUE_DAYS)


def deposit_plan(
    *,
    total: int,
    deposit: int,
    currency: str,
    session_start: date,
    installment_dates: list[date],
) -> list[tuple[int, date]]:
    """Deposit today, then the balance ten days before the start, or spread over the instalment plan."""
    if len(installment_dates) > 1:
        dates = installment_dates
        affordable = 1 + (total - deposit) // _unit(currency)
        if len(dates) > affordable:
            dates = [dates[0], dates[-1]]
        amounts = [deposit, *split_amounts(total - deposit, len(dates) - 1, currency)]
        return list(zip(amounts, dates))
    return [(deposit, installment_dates[0]), (total - deposit, reservation_balance_due_date(session_start))]


def split_amounts(total: int, count: int, currency: str) -> list[int]:
    """Split a total into instalments that add up exactly, rounded to 500 FCFA when possible."""
    if count <= 1:
        return [total]
    unit = _unit(currency)
    base = (total // count // unit) * unit
    if base <= 0:
        quotient, remainder = divmod(total, count)
        return [quotient + (1 if index < remainder else 0) for index in range(count)]
    return [base] * (count - 1) + [total - base * (count - 1)]
