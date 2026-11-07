"""Payment plans for a formation session, ported from the mother site.

Each school still chooses whether a formation can be paid in instalments and
how many at most. As on the mother site, the session's length caps that count,
the last instalment falls five days before the session ends, and two
instalments stay at least a week apart.
"""
from __future__ import annotations

import calendar
from datetime import date, timedelta
from decimal import Decimal

INSTALLMENT_FINAL_MARGIN_DAYS = 5
INSTALLMENT_MIN_INTERVAL_DAYS = 7
# Only XAF amounts are stored in whole francs (other currencies are in cents), so only
# they are rounded to 500 FCFA like on the mother site.
FCFA_CURRENCIES = frozenset({"XAF"})
FCFA_ROUNDING = 500


def installment_limit_for_session(start: date, end: date) -> int:
    """Total payment count allowed by the session's real length: 1, 2 or 3."""
    month = start.month % 12 + 1
    year = start.year + (1 if start.month == 12 else 0)
    one_month_after_start = date(year, month, min(start.day, calendar.monthrange(year, month)[1]))
    if end < one_month_after_start - timedelta(days=1) and (end - start).days + 1 < 30:
        return 1
    if end <= one_month_after_start:
        return 2
    return 3


def installment_due_dates(*, session_end: date, today: date, max_count: int) -> list[date]:
    """Due dates of each payment, the first one today."""
    if max_count <= 1:
        return [today]
    remaining = (session_end - today).days
    if remaining <= INSTALLMENT_MIN_INTERVAL_DAYS:
        return [today]
    deadline = session_end - timedelta(days=INSTALLMENT_FINAL_MARGIN_DAYS)
    available = (deadline - today).days
    if remaining <= 14:
        return [today, today + timedelta(days=max(INSTALLMENT_MIN_INTERVAL_DAYS, remaining))]
    if remaining < 30 or available < 14:
        return [today, today + timedelta(days=max(INSTALLMENT_MIN_INTERVAL_DAYS, available))]
    interval = max(INSTALLMENT_MIN_INTERVAL_DAYS, available // 2)
    dates = [today, today + timedelta(days=interval), today + timedelta(days=interval * 2)]
    return [today, dates[-1]] if max_count == 2 else dates


def session_installment_dates(
    *,
    allow_installments: bool,
    school_max_count: int,
    session_start: date,
    session_end: date,
    total: int,
    today: date,
) -> list[date]:
    """The plan offered when the student pays in instalments; a single date means none."""
    if not allow_installments or school_max_count < 2 or total <= 0:
        return [today]
    limit = min(school_max_count, installment_limit_for_session(session_start, session_end))
    return installment_due_dates(session_end=session_end, today=today, max_count=limit)


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
