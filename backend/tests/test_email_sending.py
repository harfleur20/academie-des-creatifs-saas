"""E-mails leave within the minute, never stale, open the person's space, and give the school's hour."""
import time
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from sqlalchemy import select
from test_academic_suite import build_db, ctx, seed

from app.models.entities import CommunicationOutboxRecord, FormationRecord, OrganizationRecord, UserRecord
from app.schemas.planning import CourseDayCreate
from app.services import communication_worker
from app.services.communication_delivery import _email_html, _text_body, process_communication_outbox
from app.services.organization_domains import school_base_url
from app.services.planning import create_course_day
from app.services.school_communications import queue_school_event


def queued(db, org, *, created_at: datetime) -> CommunicationOutboxRecord:
    row = CommunicationOutboxRecord(organization_id=org.id, channel="email", recipient="etudiant@test.dev",
                                    event_key="student.course.reminder_1h", subject="Cours", body="Bonjour",
                                    branding_snapshot={"school_name": "École"}, status="pending", created_at=created_at)
    db.add(row)
    db.commit()
    return row


def test_a_message_a_day_old_expires_instead_of_being_sent(monkeypatch):
    db = build_db()
    org = OrganizationRecord(name="École", slug="ecole")
    db.add(org)
    db.commit()
    now = datetime.now(UTC)
    stale = queued(db, org, created_at=now - timedelta(days=2))
    fresh = queued(db, org, created_at=now - timedelta(minutes=2))
    sent = []
    monkeypatch.setattr("app.services.communication_delivery._send_email", lambda row: sent.append(row.id))

    assert process_communication_outbox(db) == {"processed": 1, "sent": 1, "failed": 0}
    db.refresh(stale)
    db.refresh(fresh)
    assert sent == [fresh.id]
    assert (stale.status, fresh.status) == ("expired", "sent")
    assert "trop ancien" in stale.last_error


def test_a_school_message_opens_the_persons_space_and_an_invitation_keeps_its_own_link():
    db = build_db()
    org = OrganizationRecord(name="Millenium School", slug="millenium-school", subdomain="millenium")
    student = UserRecord(email="etudiant@test.dev", full_name="Francis", status="active")
    db.add_all([org, student])
    db.commit()

    email = next(row for row in queue_school_event(db, org=org, user=student, event_key="student.grade.created",
                                                   context={"grade_label": "Projet", "score_label": "16/20"})
                 if row.channel == "email")
    assert email.branding_snapshot["action_url"] == f"{school_base_url(org)}/app"
    assert "Ouvrir mon espace</a>" in _email_html(email)
    assert f'href="{school_base_url(org)}/app"' in _email_html(email)
    assert _text_body(email).endswith(f"Ouvrir mon espace : {school_base_url(org)}/app")

    invitation = queue_school_event(db, org=org, recipient_email="prof@test.dev", event_key="school.team.invitation",
                                    context={"acceptance_url": "https://millenium.test/invitation/abc"},
                                    include_whatsapp=False)[0]
    assert "action_url" not in invitation.branding_snapshot
    assert "Ouvrir mon espace" not in _email_html(invitation)


def test_the_worker_sends_on_its_own_and_only_where_it_is_enabled(monkeypatch):
    drained = []
    monkeypatch.setattr(communication_worker, "INTERVAL_SECONDS", 0.01)
    monkeypatch.setattr(communication_worker, "SessionLocal", MagicMock)
    monkeypatch.setattr(communication_worker, "process_communication_outbox", lambda db: drained.append(1))

    monkeypatch.setattr(communication_worker.settings, "communication_worker_enabled", False)
    assert communication_worker.start_communication_worker() is False

    monkeypatch.setattr(communication_worker.settings, "communication_worker_enabled", True)
    assert communication_worker.start_communication_worker() is True
    assert communication_worker.start_communication_worker() is False  # once per process
    deadline = time.monotonic() + 5
    while len(drained) < 2 and time.monotonic() < deadline:
        time.sleep(0.01)
    communication_worker.stop_communication_worker()
    assert len(drained) >= 2
    assert communication_worker._thread is None


def test_a_scheduled_live_class_is_announced_at_the_schools_hour():
    db = build_db()
    org, teacher, _student, _classmate, session, _enrollment, _other, _lesson, _day = seed(db)
    org.timezone = "Africa/Douala"  # UTC+1
    db.get(FormationRecord, session.formation_id).format_type = "live"
    db.commit()

    create_course_day(db, ctx(db, org, teacher), session.id, CourseDayCreate(
        title="Atelier", scheduled_at=datetime(2025, 1, 20, 17, 0, tzinfo=UTC), duration_minutes=90))
    emails = list(db.scalars(select(CommunicationOutboxRecord).where(
        CommunicationOutboxRecord.event_key == "student.live.scheduled", CommunicationOutboxRecord.channel == "email")))
    assert emails
    assert all("20/01/2025 à 18:00" in row.body for row in emails)
