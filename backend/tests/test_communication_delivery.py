from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.entities import CommunicationOutboxRecord, OrganizationRecord, UserRecord
from app.services.communication_delivery import process_communication_outbox
from app.api.routes.commerce import retry_communication_after_review
from app.services.school_communications import queue_school_event


def build_db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def test_branded_brevo_outbox_uses_school_sender_and_reply_to() -> None:
    db = build_db()
    org = OrganizationRecord(name="School Business", slug="school-business")
    db.add(org)
    db.flush()
    row = CommunicationOutboxRecord(
        organization_id=org.id,
        channel="email",
        recipient="student@example.com",
        event_key="student.payment.confirmed",
        subject="[School Business] Paiement confirmé",
        body="Bonjour Francis\n\nL'équipe School Business",
        branding_snapshot={
            "school_name": "School Business",
            "sender_name": "School Business",
            "reply_to_email": "contact@school.test",
            "primary_color": "#1122AA",
            "accent_color": "#172033",
            "logo_url": None,
        },
        status="pending",
    )
    db.add(row)
    db.commit()

    response = MagicMock()
    response.status_code = 201
    response.text = ""
    with patch("app.services.communication_delivery.settings") as mocked_settings, patch(
        "app.services.communication_delivery.httpx.post",
        return_value=response,
    ) as post:
        mocked_settings.email_provider = "brevo"
        mocked_settings.brevo_api_key = "test-key"
        mocked_settings.smtp_from = "notifications@platform.test"
        mocked_settings.smtp_from_name = "Académie"
        mocked_settings.brevo_api_base_url = "https://api.brevo.com/v3"
        mocked_settings.brevo_timeout_seconds = 15
        mocked_settings.smtp_host = ""
        result = process_communication_outbox(db)

    assert result == {"processed": 1, "sent": 1, "failed": 0}
    db.refresh(row)
    assert row.status == "sent"
    assert row.attempts_count == 1
    payload = post.call_args.kwargs["json"]
    assert payload["sender"] == {
        "name": "School Business",
        "email": "notifications@platform.test",
    }
    assert payload["replyTo"]["email"] == "contact@school.test"
    assert payload["headers"]["Idempotency-Key"]
    assert "School Business" in payload["htmlContent"]
    assert "Powered by Académie des Créatifs" in payload["htmlContent"]


def test_failed_outbox_is_retryable_and_records_error() -> None:
    db = build_db()
    org = OrganizationRecord(name="School", slug="school")
    db.add(org)
    db.flush()
    row = CommunicationOutboxRecord(
        organization_id=org.id,
        channel="email",
        recipient="student@example.com",
        event_key="test",
        subject="Test",
        body="Test",
        branding_snapshot={"school_name": "School"},
        status="pending",
    )
    db.add(row)
    db.commit()

    with patch("app.services.communication_delivery.settings") as mocked_settings:
        mocked_settings.email_provider = "brevo"
        mocked_settings.brevo_api_key = ""
        mocked_settings.smtp_from = ""
        mocked_settings.smtp_host = ""
        result = process_communication_outbox(db)

    assert result == {"processed": 1, "sent": 0, "failed": 1}
    db.refresh(row)
    assert row.status == "failed"
    assert row.attempts_count == 1
    assert "non configuré" in (row.last_error or "")


def test_second_worker_cannot_send_claimed_message(tmp_path) -> None:
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'outbox.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    first = Session(engine, expire_on_commit=False)
    second = Session(engine, expire_on_commit=False)
    org = OrganizationRecord(name="School", slug="school")
    first.add(org)
    first.flush()
    row = CommunicationOutboxRecord(organization_id=org.id, channel="email", recipient="student@example.com", event_key="test", subject="Test", body="Test", branding_snapshot={}, status="pending")
    first.add(row)
    first.commit()
    sends = []

    def send(_row):
        sends.append(_row.id)
        assert process_communication_outbox(second) == {"processed": 0, "sent": 0, "failed": 0}

    with patch("app.services.communication_delivery._send_email", side_effect=send):
        assert process_communication_outbox(first) == {"processed": 1, "sent": 1, "failed": 0}
    assert sends == [row.id]
    first.refresh(row)
    assert row.status == "sent"


def test_interrupted_or_uncertain_send_requires_review(tmp_path) -> None:
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'outbox.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    db = Session(engine, expire_on_commit=False)
    org = OrganizationRecord(name="School", slug="school")
    db.add(org)
    db.flush()
    interrupted = CommunicationOutboxRecord(organization_id=org.id, channel="email", recipient="one@example.com", event_key="test", subject="Test", body="Test", branding_snapshot={}, status="sending", claimed_at=datetime.now(UTC) - timedelta(minutes=11), claim_token="old")
    uncertain = CommunicationOutboxRecord(organization_id=org.id, channel="email", recipient="two@example.com", event_key="test", subject="Test", body="Test", branding_snapshot={}, status="pending")
    db.add_all([interrupted, uncertain])
    db.commit()

    with patch("app.services.communication_delivery._send_email", side_effect=httpx.ReadTimeout("timeout")) as send:
        assert process_communication_outbox(db) == {"processed": 1, "sent": 0, "failed": 1}
        assert process_communication_outbox(db) == {"processed": 0, "sent": 0, "failed": 0}
    assert send.call_count == 1
    db.refresh(interrupted)
    db.refresh(uncertain)
    assert interrupted.status == uncertain.status == "needs_review"
    retry_communication_after_review(interrupted.id, db, SimpleNamespace(
        support_mode=False, organization_roles={"manager"}, organization_id=org.id,
    ))
    db.refresh(interrupted)
    assert interrupted.status == "pending"


def test_exhausted_local_retries_are_visible_for_review() -> None:
    db = build_db()
    org = OrganizationRecord(name="School", slug="retry-school")
    db.add(org)
    db.flush()
    row = CommunicationOutboxRecord(organization_id=org.id, channel="email", recipient="student@example.com", event_key="test", subject="Test", body="Test", branding_snapshot={}, status="failed", attempts_count=2)
    db.add(row)
    db.commit()
    with patch("app.services.communication_delivery._send_email", side_effect=RuntimeError("Fournisseur e-mail non configuré.")):
        assert process_communication_outbox(db) == {"processed": 1, "sent": 0, "failed": 1}
    db.refresh(row)
    assert row.attempts_count == 3
    assert row.status == "needs_review"



def test_central_school_template_queues_email_and_whatsapp() -> None:
    db = build_db()
    org = OrganizationRecord(name="School Business", slug="school-business")
    user = UserRecord(
        email="student@example.com",
        full_name="Francis Test",
        phone="+237680950319",
        status="active",
    )
    db.add_all([org, user])
    db.commit()

    rows = queue_school_event(
        db,
        org=org,
        user=user,
        event_key="student.assignment.created",
        context={
            "assignment_title": "Projet final",
            "session_label": "Octobre 2026",
            "due_at": "30/10/2026 18:00",
        },
    )
    db.commit()

    assert {row.channel for row in rows} == {"email", "whatsapp"}
    email = next(row for row in rows if row.channel == "email")
    assert email.event_key == "student.assignment.created"
    assert "School Business" in (email.subject or "")
    assert "Projet final" in email.body
    assert "30/10/2026 18:00" in email.body
    assert email.branding_snapshot["school_name"] == "School Business"
