from datetime import UTC, datetime

import jwt
import pytest
from fastapi import HTTPException
from test_academic_suite import build_db, ctx, seed

from app.core.config import settings
from app.models.entities import FormationRecord
from app.services.live_classes import join_live_class, live_provider_configured

SECRET = "s" * 48
NOW = datetime(2025, 1, 10, 9, 5, tzinfo=UTC)  # during the seeded course day


@pytest.fixture
def self_hosted(monkeypatch):
    monkeypatch.setattr(settings, "live_provider", "jitsi")
    monkeypatch.setattr(settings, "jitsi_domain", "live.ecole.test")
    monkeypatch.setattr(settings, "jitsi_app_id", "academie-live")
    monkeypatch.setattr(settings, "jitsi_app_secret", SECRET)
    monkeypatch.setattr(settings, "jitsi_xmpp_domain", "meet.jitsi")
    monkeypatch.setattr(settings, "jaas_enabled", False)
    # The teacher profile check is covered elsewhere.
    monkeypatch.setattr("app.services.live_classes.require_teacher_ready", lambda db, tenant: None)


# Production also requires its private B2 bucket and Cloudinary: give it both, so these
# tests reach the live checks.
PRODUCTION_STORAGE = {
    "storage_provider": "b2",
    "b2_endpoint_url": "https://s3.eu-central-003.backblazeb2.com",
    "b2_region": "eu-central-003",
    "b2_private_bucket_name": "private",
    "b2_access_key_id": "test-id",
    "b2_secret_access_key": "test-secret",
    "public_asset_provider": "cloudinary",
    "cloudinary_cloud_name": "test-cloud",
    "cloudinary_api_key": "test-key",
    "cloudinary_api_secret": "test-secret",
}


def production(monkeypatch) -> None:
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "jwt_secret_key", "k" * 40)
    monkeypatch.setattr(settings, "jaas_recording_enabled", False)
    for name, value in PRODUCTION_STORAGE.items():
        monkeypatch.setattr(settings, name, value)


def live_school():
    db = build_db()
    org, teacher, student, _classmate, session, _e, _ce, _lesson, day = seed(db)
    db.get(FormationRecord, session.formation_id).format_type = "live"
    db.commit()
    return db, org, teacher, student, session, day


def claims(token: str) -> dict:
    return jwt.decode(token, SECRET, algorithms=["HS256"], audience="academie-live",
                      options={"verify_exp": False, "verify_nbf": False})


def test_a_self_hosted_room_uses_the_school_domain_and_a_shared_secret(self_hosted) -> None:
    db, org, teacher, student, session, day = live_school()
    joined = join_live_class(db, ctx(db, org, student), day.id, now=NOW)
    room = f"school-{org.id}-session-{session.id}-day-{day.id}"
    assert joined["domain"] == "live.ecole.test"
    assert joined["room_name"] == room  # no JaaS tenant prefix
    assert joined["external_api_url"] == "https://live.ecole.test/external_api.js"

    student_claims = claims(joined["token"])
    assert (student_claims["iss"], student_claims["sub"], student_claims["room"]) == ("academie-live", "meet.jitsi", room)
    assert student_claims["exp"] - int(NOW.timestamp()) == 600
    assert student_claims["context"]["user"]["moderator"] is False
    assert student_claims["context"]["user"]["affiliation"] == "member"
    assert student_claims["context"]["features"]["recording"] is False
    # Students share their screen too, as the teacher does.
    assert student_claims["context"]["features"]["screen-sharing"] == "true"

    teacher_claims = claims(join_live_class(db, ctx(db, org, teacher), day.id, now=NOW)["token"])
    assert teacher_claims["context"]["user"]["moderator"] is True
    assert teacher_claims["context"]["user"]["affiliation"] == "owner"
    assert teacher_claims["context"]["features"]["screen-sharing"] == "true"


def test_a_token_signed_with_another_secret_is_rejected(self_hosted) -> None:
    db, org, _teacher, student, _session, day = live_school()
    token = join_live_class(db, ctx(db, org, student), day.id, now=NOW)["token"]
    with pytest.raises(jwt.InvalidSignatureError):
        jwt.decode(token, "x" * 48, algorithms=["HS256"], audience="academie-live", options={"verify_exp": False})


def test_an_incomplete_self_hosted_setup_keeps_the_room_closed(self_hosted, monkeypatch) -> None:
    monkeypatch.setattr(settings, "jitsi_app_secret", "")
    assert live_provider_configured() is False
    db, org, _teacher, student, _session, day = live_school()
    with pytest.raises(HTTPException) as closed:
        join_live_class(db, ctx(db, org, student), day.id, now=NOW)
    assert closed.value.status_code == 503


@pytest.mark.parametrize(("provider", "secret", "message"), [
    ("jitsi", "court", "JITSI_APP_SECRET"),
    ("zoom", SECRET, "LIVE_PROVIDER"),
])
def test_production_refuses_a_weak_or_unknown_live_setup(monkeypatch, provider, secret, message) -> None:
    production(monkeypatch)
    monkeypatch.setattr(settings, "live_provider", provider)
    monkeypatch.setattr(settings, "jitsi_domain", "live.ecole.test")
    monkeypatch.setattr(settings, "jitsi_app_id", "academie-live")
    monkeypatch.setattr(settings, "jitsi_app_secret", secret)
    with pytest.raises(RuntimeError) as refused:
        settings.validate_production_security()
    assert message in str(refused.value)


def test_production_accepts_a_complete_self_hosted_setup(self_hosted, monkeypatch) -> None:
    production(monkeypatch)
    settings.validate_production_security()


def test_jitsi_gets_each_room_its_school_identity(self_hosted) -> None:
    from fastapi import Response

    from app.api.routes.planning import read_self_hosted_room_branding

    db, org, _teacher, _student, session, day = live_school()
    org.logo_url = "https://ecole.test/logo.png"
    org.primary_color = "#1f2559"
    db.commit()
    response = Response()
    room = f"school-{org.id}-session-{session.id}-day-{day.id}"
    assert read_self_hosted_room_branding(response, room, db) == {
        "backgroundColor": "#1f2559", "logoImageUrl": "https://ecole.test/logo.png",
    }
    # Jitsi asks from its own domain, without cookies.
    assert response.headers["access-control-allow-origin"] == "https://live.ecole.test"

    for forged in (f"school-{org.id + 1}-session-{session.id}-day-{day.id}", "autre-salle", f"academie-live/{room}"):
        with pytest.raises(HTTPException) as missing:
            read_self_hosted_room_branding(Response(), forged, db)
        assert missing.value.status_code == 404


def test_room_identity_is_off_without_the_self_hosted_live(self_hosted, monkeypatch) -> None:
    from fastapi import Response

    from app.api.routes.planning import read_self_hosted_room_branding

    db, org, _teacher, _student, session, day = live_school()
    monkeypatch.setattr(settings, "live_provider", "jaas")
    with pytest.raises(HTTPException) as off:
        read_self_hosted_room_branding(Response(), f"school-{org.id}-session-{session.id}-day-{day.id}", db)
    assert off.value.status_code == 404
