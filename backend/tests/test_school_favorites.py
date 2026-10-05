import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.entities import FormationRecord, OrganizationRecord, UserRecord
from app.services.school_favorites import add_school_favorite, list_school_favorites, remove_school_favorite


def test_favorites_are_scoped_to_school_and_user_and_hide_unpublished_formations():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        user = UserRecord(email="student@example.test", full_name="Student", status="active")
        other_user = UserRecord(email="other@example.test", full_name="Other", status="active")
        first = OrganizationRecord(name="First", slug="first", status="active", is_active=True)
        second = OrganizationRecord(name="Second", slug="second", status="active", is_active=True)
        db.add_all([user, other_user, first, second])
        db.flush()

        def formation(org: OrganizationRecord, slug: str, title: str, status: str = "published") -> FormationRecord:
            return FormationRecord(
                organization_id=org.id, slug=slug, title=title, status=status,
                description="A complete formation", cover_image_url="https://example.test/cover.jpg",
                public_program="Module one", price_cents=10000,
            )

        db.add_all([
            formation(first, "design", "First design"),
            formation(second, "design", "Second design"),
            formation(first, "draft", "Draft", "draft"),
        ])
        db.commit()

        assert [item.title for item in add_school_favorite(db, first, user, "design")] == ["First design"]
        assert len(add_school_favorite(db, first, user, "design")) == 1
        assert list_school_favorites(db, first, other_user) == []
        assert list_school_favorites(db, second, user) == []
        assert [item.title for item in add_school_favorite(db, second, user, "design")] == ["Second design"]
        with pytest.raises(HTTPException) as exc:
            add_school_favorite(db, first, user, "draft")
        assert exc.value.status_code == 404
        first_design = db.scalar(select(FormationRecord).where(FormationRecord.organization_id == first.id, FormationRecord.slug == "design"))
        assert first_design is not None
        first_design.status = "draft"
        db.commit()
        assert list_school_favorites(db, first, user) == []
        first_design.status = "published"
        db.commit()
        assert remove_school_favorite(db, first, user, "design") == []
        assert [item.title for item in list_school_favorites(db, second, user)] == ["Second design"]
