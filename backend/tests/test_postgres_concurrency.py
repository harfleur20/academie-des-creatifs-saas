"""Production database locking checks; run with TEST_POSTGRES_URL set."""

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import (
    CommunicationOutboxRecord,
    FormationRecord,
    FormationSessionRecord,
    OrganizationRecord,
    OrganizationStudentProfileRecord,
    StudentOrderRecord,
    UserRecord,
)
from app.schemas.commerce import CheckoutCreate
from app.services import school_branding
from app.services.communication_delivery import process_communication_outbox
from app.services.school_branding import get_or_create_identity_records
from app.services.school_commerce import confirm_demo_checkout, create_checkout


POSTGRES_URL = os.getenv("TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not POSTGRES_URL, reason="TEST_POSTGRES_URL is required")


@pytest.fixture
def postgres_engine(monkeypatch):
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "payment_mode", "demo")
    monkeypatch.setattr(settings, "allow_demo_payments", True)
    engine = create_engine(POSTGRES_URL, pool_size=5, max_overflow=5)
    try:
        yield engine
    finally:
        engine.dispose()


def _seed(engine, *, capacity=1):
    suffix = uuid4().hex[:10]
    with Session(engine) as db:
        org = OrganizationRecord(
            name="Concurrent school",
            slug=f"concurrent-{suffix}",
            subdomain=f"concurrent-{suffix}",
            status="active",
            is_active=True,
            contact_email=f"contact-{suffix}@test.dev",
        )
        users = [UserRecord(email=f"{suffix}-{i}@test.dev", full_name=f"Student {i}", status="active") for i in range(2)]
        db.add_all([org, *users])
        db.flush()

        site, legal, *_ = get_or_create_identity_records(db, org)
        site.student_code_prefix = "CS"
        site.student_code_prefix_confirmed_at = datetime.now(UTC)
        site.legal_notice = "Mentions légales de l'école de test"
        site.sales_terms = "Conditions générales de vente de l'école de test"
        site.privacy_policy = "Politique de confidentialité de l'école de test"
        site.refund_policy = "Politique de remboursement de l'école de test"
        site.is_published = True
        legal.legal_name = "Concurrent School Test"
        legal.legal_address = "1 rue des Tests"
        legal.invoice_email = f"billing-{suffix}@test.dev"

        formation = FormationRecord(
            organization_id=org.id,
            slug="course",
            title="Course",
            description="Concurrent course",
            cover_image_url="https://example.test/course.jpg",
            public_program="Programme de test",
            status="published",
            format_type="live",
            price_cents=1000,
            currency="XAF",
        )
        db.add(formation)
        db.flush()
        session = FormationSessionRecord(organization_id=org.id, formation_id=formation.id, label="Future", start_date=(datetime.now(UTC) + timedelta(days=2)).date(), end_date=(datetime.now(UTC) + timedelta(days=60)).date(), seat_capacity=capacity, status="open")
        db.add(session)
        db.commit()
        return org.id, [user.id for user in users], session.id


def test_two_checkouts_cannot_reserve_the_same_seat(postgres_engine):
    org_id, user_ids, session_id = _seed(postgres_engine)
    gate = threading.Barrier(2)

    def checkout(user_id):
        with Session(postgres_engine, expire_on_commit=False) as db:
            org = db.get(OrganizationRecord, org_id)
            user = db.get(UserRecord, user_id)
            gate.wait(timeout=10)
            try:
                return create_checkout(db, org, user, CheckoutCreate(session_id=session_id)).order_id
            except HTTPException as exc:
                return exc.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(checkout, user_ids))
    assert len([result for result in results if result != 409]) == 1
    assert results.count(409) == 1
    with Session(postgres_engine) as db:
        orders = db.scalars(select(StudentOrderRecord).where(StudentOrderRecord.session_id == session_id)).all()
        assert len(orders) == 1


def test_concurrent_payments_allocate_distinct_student_codes(postgres_engine):
    org_id, user_ids, session_id = _seed(postgres_engine, capacity=2)
    with Session(postgres_engine, expire_on_commit=False) as db:
        org = db.get(OrganizationRecord, org_id)
        order_ids = [create_checkout(db, org, db.get(UserRecord, user_id), CheckoutCreate(session_id=session_id)).order_id for user_id in user_ids]
    gate = threading.Barrier(2)

    def pay(order_id, user_id):
        with Session(postgres_engine, expire_on_commit=False) as db:
            gate.wait(timeout=10)
            return confirm_demo_checkout(db, db.get(OrganizationRecord, org_id), db.get(UserRecord, user_id), order_id).status

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda pair: pay(*pair), zip(order_ids, user_ids)))
    assert results == ["paid", "paid"]
    with Session(postgres_engine) as db:
        codes = db.scalars(select(OrganizationStudentProfileRecord.student_code).where(OrganizationStudentProfileRecord.organization_id == org_id)).all()
        assert len(codes) == len(set(codes)) == 2


def test_two_first_visits_create_one_identity_per_school(postgres_engine, monkeypatch):
    suffix = uuid4().hex[:10]
    with Session(postgres_engine) as db:
        org = OrganizationRecord(name="Fresh school", slug=f"fresh-{suffix}", subdomain=f"fresh-{suffix}")
        db.add(org)
        db.commit()
        org_id = org.id
    gate = threading.Barrier(2)
    local = threading.local()
    real_find = school_branding._find_identity_record

    def find_then_wait(db, model, organization_id):
        found = real_find(db, model, organization_id)
        if not getattr(local, "waited", False):
            local.waited = True
            gate.wait(timeout=10)  # both visits have found the public site missing
        return found

    monkeypatch.setattr(school_branding, "_find_identity_record", find_then_wait)

    def visit():
        local.waited = False
        with Session(postgres_engine, autoflush=False, expire_on_commit=False) as db:
            return [record.id for record in get_or_create_identity_records(db, db.get(OrganizationRecord, org_id))]

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = [future.result() for future in [pool.submit(visit) for _ in range(2)]]
    assert first == second
    with Session(postgres_engine) as db:
        for model, _defaults in school_branding.IDENTITY_RECORDS:
            assert len(db.scalars(select(model.id).where(model.organization_id == org_id)).all()) == 1


def test_two_workers_send_one_outbox_message(postgres_engine):
    org_id, _users, _session_id = _seed(postgres_engine)
    with Session(postgres_engine) as db:
        row = CommunicationOutboxRecord(organization_id=org_id, channel="email", recipient="student@example.com", event_key="test", subject="Test", body="Test", branding_snapshot={}, status="pending")
        db.add(row)
        db.commit()
        row_id = row.id
    gate = threading.Barrier(2)
    calls = []
    lock = threading.Lock()

    def send(row):
        with lock:
            calls.append(row.id)
        time.sleep(0.2)

    def work():
        with Session(postgres_engine, expire_on_commit=False) as db:
            gate.wait(timeout=10)
            return process_communication_outbox(db, organization_id=org_id)

    with patch("app.services.communication_delivery._send_email", side_effect=send):
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: work(), range(2)))
    assert sum(result["processed"] for result in results) == 1
    assert calls == [row_id]
    with Session(postgres_engine) as db:
        assert db.get(CommunicationOutboxRecord, row_id).status == "sent"
