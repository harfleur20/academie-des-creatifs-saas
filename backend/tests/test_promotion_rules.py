from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from app.schemas.commerce import PromotionCreate, PromotionRead


def window():
    start = datetime(2026, 10, 7, tzinfo=UTC)
    return start, start + timedelta(days=7)


def test_new_promotion_uses_system_name_and_requires_one_target() -> None:
    start, end = window()
    promotion = PromotionCreate(
        name="Rentrée personnalisée",
        formation_id=10,
        discount_type="percentage",
        discount_value=20,
        starts_at=start,
        ends_at=end,
    )
    assert promotion.name == "%Promo"
    assert promotion.formation_id == 10
    assert promotion.session_id is None

    with pytest.raises(ValidationError):
        PromotionCreate(
            formation_id=10,
            session_id=20,
            discount_type="percentage",
            discount_value=20,
            starts_at=start,
            ends_at=end,
        )


def test_new_promotion_requires_valid_dates_and_percentage() -> None:
    start, end = window()
    with pytest.raises(ValidationError):
        PromotionCreate(
            formation_id=10,
            discount_type="percentage",
            discount_value=101,
            starts_at=start,
            ends_at=end,
        )

    with pytest.raises(ValidationError):
        PromotionCreate(
            formation_id=10,
            discount_type="percentage",
            discount_value=20,
            starts_at=end,
            ends_at=start,
        )


def test_legacy_promotion_without_dates_remains_readable() -> None:
    promotion = PromotionRead(
        id=1,
        name="Ancienne promo",
        formation_id=10,
        session_id=None,
        discount_type="percentage",
        discount_value=15,
        starts_at=None,
        ends_at=None,
        max_uses=None,
        uses_count=3,
        is_active=True,
        created_at=datetime(2026, 9, 1, tzinfo=UTC),
    )
    assert promotion.starts_at is None
    assert promotion.ends_at is None
