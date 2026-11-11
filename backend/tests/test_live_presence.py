from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from test_academic_suite import build_db, ctx, seed

from app.core.config import settings
from app.models.entities import AttendanceRecord, FormationRecord, LiveRoomPresenceRecord
from app.schemas.planning import CourseDayReportSubmit
from app.services.live_classes import heartbeat_live_class, join_live_class, leave_live_class, start_live_class
from app.services.planning import submit_course_day_report

START = datetime(2025, 1, 10, 9, 0, tzinfo=UTC)  # the seeded course day


@pytest.fixture(autouse=True)
def self_hosted(monkeypatch):
    monkeypatch.setattr(settings, "live_provider", "jitsi")
    monkeypatch.setattr(settings, "jitsi_domain", "live.ecole.test")
    monkeypatch.setattr(settings, "jitsi_app_id", "academie-live")
    monkeypatch.setattr(settings, "jitsi_app_secret", "s" * 48)
    # The teacher profile check is covered elsewhere.
    monkeypatch.setattr("app.services.live_classes.require_teacher_ready", lambda db, tenant: None)


def live_school():
    db = build_db()
    org, teacher, student, classmate, session, enrollment, classmate_enrollment, _lesson, day = seed(db)
    db.get(FormationRecord, session.formation_id).format_type = "live"
    db.commit()
    return db, org, teacher, student, classmate, enrollment, classmate_enrollment, day


def join(db, tenant, day, device, minutes):
    return join_live_class(db, tenant, day.id, now=START + timedelta(minutes=minutes), device_id=device, device_label="Edge")


def test_a_student_keeps_one_device_in_live_classes() -> None:
    db, org, _teacher, student, *_rest, day = live_school()
    tenant = ctx(db, org, student)
    join(db, tenant, day, "phone", 1)
    with pytest.raises(HTTPException) as taken:
        join(db, tenant, day, "laptop", 2)
    assert taken.value.status_code == 409
    assert "autre appareil" in taken.value.detail

    join(db, tenant, day, "phone", 2)  # the same device comes back freely
    heartbeat_live_class(db, tenant, day.id, now=START + timedelta(minutes=3), device_id="phone")
    with pytest.raises(HTTPException):
        join(db, tenant, day, "laptop", 4)

    leave_live_class(db, tenant, day.id, now=START + timedelta(minutes=4), device_id="phone")
    join(db, tenant, day, "laptop", 4)  # leaving frees the place at once


def test_a_silent_device_frees_the_place_after_90_seconds() -> None:
    db, org, _teacher, student, *_rest, day = live_school()
    tenant = ctx(db, org, student)
    join(db, tenant, day, "phone", 1)
    with pytest.raises(HTTPException):
        join_live_class(db, tenant, day.id, now=START + timedelta(minutes=1, seconds=80), device_id="laptop")
    join_live_class(db, tenant, day.id, now=START + timedelta(minutes=1, seconds=91), device_id="laptop")


def test_the_teacher_is_not_held_to_one_device() -> None:
    db, org, teacher, *_rest, day = live_school()
    tenant = ctx(db, org, teacher)
    join(db, tenant, day, "phone", 1)
    join(db, tenant, day, "laptop", 1)
    assert db.scalars(select(LiveRoomPresenceRecord)).all() == []


def test_a_closed_class_stops_the_heartbeat() -> None:
    db, org, teacher, student, *_rest, day = live_school()
    tenant = ctx(db, org, student)
    join(db, tenant, day, "phone", 1)
    start_live_class(db, ctx(db, org, teacher), day.id, now=START)
    submit_course_day_report(db, ctx(db, org, teacher), day.id, CourseDayReportSubmit(
        delivery_status="held", summary="Cours terminé en avance",
    ), now=START + timedelta(minutes=30))
    with pytest.raises(HTTPException) as closed:
        heartbeat_live_class(db, tenant, day.id, now=START + timedelta(minutes=31), device_id="phone")
    assert closed.value.status_code == 404
    leave_live_class(db, tenant, day.id, now=START + timedelta(minutes=31), device_id="phone")  # still allowed


def test_the_report_marks_who_entered_the_room() -> None:
    db, org, teacher, student, classmate, enrollment, classmate_enrollment, day = live_school()
    start_live_class(db, ctx(db, org, teacher), day.id, now=START + timedelta(minutes=2))
    join(db, ctx(db, org, student), day, "phone", 5)
    join(db, ctx(db, org, classmate), day, "laptop", 20)  # more than 15 minutes after the start
    submit_course_day_report(db, ctx(db, org, teacher), day.id, CourseDayReportSubmit(
        delivery_status="held", summary="Cours tenu jusqu'au bout",
    ), now=START + timedelta(minutes=60))
    marks = dict(db.execute(select(AttendanceRecord.enrollment_id, AttendanceRecord.status).where(
        AttendanceRecord.course_day_id == day.id,
    )).all())
    assert marks == {enrollment.id: "present", classmate_enrollment.id: "late"}


def test_a_student_who_never_entered_is_absent() -> None:
    db, org, teacher, student, _classmate, enrollment, classmate_enrollment, day = live_school()
    start_live_class(db, ctx(db, org, teacher), day.id, now=START)
    join(db, ctx(db, org, student), day, "phone", 1)
    submit_course_day_report(db, ctx(db, org, teacher), day.id, CourseDayReportSubmit(
        delivery_status="partial", summary="Cours écourté par une coupure",
    ), now=START + timedelta(minutes=40))
    marks = dict(db.execute(select(AttendanceRecord.enrollment_id, AttendanceRecord.status).where(
        AttendanceRecord.course_day_id == day.id,
    )).all())
    assert marks == {enrollment.id: "present", classmate_enrollment.id: "absent"}
