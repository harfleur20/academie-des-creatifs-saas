"""A formation's presentation video: only one imported for the school, and nothing left behind."""
import pytest
from fastapi import HTTPException
from test_publication_readiness import owner_school, publish_site

from app.core.config import settings
from app.models.entities import FormationRecord
from app.schemas.formations import FormationCreate, FormationUpdate
from app.services import assets
from app.services.assets import presentation_video_location
from app.services.formations import create_formation, update_formation


def stored_video(tmp_path, organization_id: int, name: str) -> tuple[str, object]:
    path = tmp_path / "schools" / str(organization_id) / "presentations" / f"{name * 32}.mp4"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x00\x00\x00\x18ftypmp42")
    return f"{settings.backend_public_url}/uploads/schools/{organization_id}/presentations/{name * 32}.mp4", path


def test_only_a_video_stored_for_the_school_is_accepted():
    _db, org, _owner, _tenant = owner_school()
    base = f"{settings.backend_public_url}/uploads"
    assert presentation_video_location(f"{base}/schools/{org.id}/presentations/{'b' * 32}.mp4", org.id)
    for foreign in (
        "https://tracker.example/video.mp4",
        f"{base}/schools/{org.id + 1}/presentations/{'b' * 32}.mp4",  # another school's
        f"{base}/schools/{org.id}/presentations/../brand/{'b' * 32}.mp4",
        f"{base}/schools/{org.id}/presentations/intro.mp4",
    ):
        assert presentation_video_location(foreign, org.id) is None, foreign


def test_an_outside_address_is_refused_when_saving_a_formation():
    db, _org, _owner, tenant = owner_school()
    publish_site(db, tenant)
    with pytest.raises(HTTPException) as refused:
        create_formation(db, tenant, FormationCreate(
            slug="motion", title="Motion", description="Motion", format_type="live",
            presentation_video_url="https://tracker.example/video.mp4",
        ))
    assert refused.value.status_code == 422
    formation = create_formation(db, tenant, FormationCreate(slug="motion", title="Motion", description="Motion", format_type="live"))
    with pytest.raises(HTTPException) as refused:
        update_formation(db, tenant, formation.id, FormationUpdate(presentation_video_url="javascript:alert(1)"))
    assert refused.value.status_code == 422


def test_a_replaced_or_removed_video_is_deleted_unless_still_shown(tmp_path, monkeypatch):
    db, org, _owner, tenant = owner_school()
    publish_site(db, tenant)
    monkeypatch.setattr(assets, "UPLOADS_ROOT", tmp_path)
    first, first_file = stored_video(tmp_path, org.id, "a")
    second, second_file = stored_video(tmp_path, org.id, "b")
    formation = create_formation(db, tenant, FormationCreate(
        slug="motion", title="Motion", description="Motion", format_type="live", presentation_video_url=first,
    ))
    twin = create_formation(db, tenant, FormationCreate(
        slug="motion-2", title="Motion 2", description="Motion", format_type="live", presentation_video_url=first,
    ))

    # Replaced, but the other formation still shows it: kept.
    update_formation(db, tenant, formation.id, FormationUpdate(presentation_video_url=second))
    assert first_file.exists()
    # Removed from the last formation that showed it: deleted.
    update_formation(db, tenant, twin.id, FormationUpdate(presentation_video_url=None))
    assert not first_file.exists()
    assert db.get(FormationRecord, twin.id).presentation_video_url is None
    # Saving the formation again with the same video changes nothing.
    update_formation(db, tenant, formation.id, FormationUpdate(presentation_video_url=second, title="Motion design"))
    assert second_file.exists()
