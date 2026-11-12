from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from test_academic_suite import build_db, ctx, seed

from app.core.config import settings
from app.models.entities import AttendanceRecord, FormationRecord, LiveRoomPresenceRecord
from app.schemas.planning import CourseDayReportSubmit
from app.services.live_classes import (
    LiveEvidence, answer_roll_call, heartbeat_live_class, join_live_class, leave_live_class, prefill_live_status,
    start_live_class, start_roll_call,
)
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


def stay(db, tenant, day, device, from_minute, to_minute):
    """A student in the room: joins, then a heartbeat every 30 seconds until leaving."""
    join(db, tenant, day, device, from_minute)
    moment = START + timedelta(minutes=from_minute)
    while moment < START + timedelta(minutes=to_minute):
        moment += timedelta(seconds=30)
        heartbeat_live_class(db, tenant, day.id, now=moment, device_id=device)
    leave_live_class(db, tenant, day.id, now=moment, device_id=device)


def report(db, org, teacher, day, minutes, status="held"):
    submit_course_day_report(db, ctx(db, org, teacher), day.id, CourseDayReportSubmit(
        delivery_status=status, summary="Compte rendu de la séance",
    ), now=START + timedelta(minutes=minutes))
    return dict(db.execute(select(AttendanceRecord.enrollment_id, AttendanceRecord.status).where(
        AttendanceRecord.course_day_id == day.id,
    )).all())


def test_the_report_marks_who_followed_the_class() -> None:
    db, org, teacher, student, classmate, enrollment, classmate_enrollment, day = live_school()
    start_live_class(db, ctx(db, org, teacher), day.id, now=START + timedelta(minutes=2))
    stay(db, ctx(db, org, student), day, "phone", 5, 55)
    stay(db, ctx(db, org, classmate), day, "laptop", 20, 55)  # came in more than 15 minutes after the start
    assert report(db, org, teacher, day, 60) == {enrollment.id: "present", classmate_enrollment.id: "late"}


def test_a_short_visit_is_not_a_presence() -> None:
    db, org, teacher, student, classmate, enrollment, classmate_enrollment, day = live_school()
    start_live_class(db, ctx(db, org, teacher), day.id, now=START)
    stay(db, ctx(db, org, student), day, "phone", 1, 12)  # 11 minutes of a 60-minute course
    stay(db, ctx(db, org, classmate), day, "laptop", 1, 58)
    assert report(db, org, teacher, day, 60) == {enrollment.id: "absent", classmate_enrollment.id: "present"}


def test_a_dropped_connection_only_loses_the_gap() -> None:
    db, org, _teacher, student, *_rest, day = live_school()
    tenant = ctx(db, org, student)
    join(db, tenant, day, "phone", 0)
    heartbeat_live_class(db, tenant, day.id, now=START + timedelta(seconds=30), device_id="phone")
    heartbeat_live_class(db, tenant, day.id, now=START + timedelta(minutes=10), device_id="phone")  # 9.5 min silent
    presence = db.scalar(select(LiveRoomPresenceRecord))
    assert presence.seconds_in_room == 30 + 60


def test_a_student_who_never_entered_is_absent() -> None:
    db, org, teacher, student, _classmate, enrollment, classmate_enrollment, day = live_school()
    start_live_class(db, ctx(db, org, teacher), day.id, now=START)
    stay(db, ctx(db, org, student), day, "phone", 1, 39)
    assert report(db, org, teacher, day, 40, "partial") == {enrollment.id: "present", classmate_enrollment.id: "absent"}


def test_the_roll_call_tells_who_is_really_there() -> None:
    db, org, teacher, student, classmate, enrollment, classmate_enrollment, day = live_school()
    teacher_tenant = ctx(db, org, teacher)
    with pytest.raises(HTTPException) as not_started:
        start_roll_call(db, teacher_tenant, day.id, now=START)
    assert not_started.value.status_code == 409
    start_live_class(db, teacher_tenant, day.id, now=START)
    with pytest.raises(HTTPException) as student_call:
        start_roll_call(db, ctx(db, org, student), day.id, now=START)
    assert student_call.value.status_code == 403
    stay(db, ctx(db, org, student), day, "phone", 1, 19)
    stay(db, ctx(db, org, classmate), day, "laptop", 1, 19)

    call = start_roll_call(db, teacher_tenant, day.id, now=START + timedelta(minutes=20))
    assert call["open"] and call["answers_count"] == 0
    assert start_roll_call(db, teacher_tenant, day.id, now=START + timedelta(minutes=21))["id"] == call["id"]
    seen = heartbeat_live_class(db, ctx(db, org, student), day.id, now=START + timedelta(minutes=20, seconds=30), device_id="phone")
    assert seen["roll_call"]["id"] == call["id"] and not seen["roll_call"]["answered"]
    answer_roll_call(db, ctx(db, org, classmate), day.id, call["id"], now=START + timedelta(minutes=21))
    with pytest.raises(HTTPException) as late_answer:
        answer_roll_call(db, ctx(db, org, student), day.id, call["id"], now=START + timedelta(minutes=23))
    assert late_answer.value.status_code == 409
    assert heartbeat_live_class(db, teacher_tenant, day.id, now=START + timedelta(minutes=23))["roll_call"]["answers_count"] == 1
    assert heartbeat_live_class(db, ctx(db, org, student), day.id, now=START + timedelta(minutes=23), device_id="phone")["roll_call"] is None

    # Both stayed the whole course; only the one who answered the roll call is present.
    stay(db, ctx(db, org, student), day, "phone", 24, 59)
    stay(db, ctx(db, org, classmate), day, "laptop", 24, 59)
    assert report(db, org, teacher, day, 60) == {enrollment.id: "absent", classmate_enrollment.id: "present"}


def test_the_prefill_rules() -> None:
    start, end = START, START + timedelta(minutes=60)
    on_time = LiveEvidence(entered_at=START + timedelta(minutes=2), seconds_in_room=40 * 60, roll_calls_answered=1)
    assert prefill_live_status(None, 0, start, end) == "absent"
    assert prefill_live_status(on_time, 1, start, end) == "present"
    assert prefill_live_status(on_time, 0, start, end) == "present"
    assert prefill_live_status(LiveEvidence(START + timedelta(minutes=16), 40 * 60, 1), 1, start, end) == "late"
    assert prefill_live_status(LiveEvidence(START, 29 * 60, 1), 1, start, end) == "absent"  # under half of the course
    assert prefill_live_status(LiveEvidence(START, 55 * 60, 0), 2, start, end) == "absent"  # no answer to any roll call
