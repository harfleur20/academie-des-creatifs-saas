from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_tenant_context
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.entities import (
    EnrollmentRecord,
    FormationRecord,
    FormationSessionRecord,
    GradeRecord,
    OrganizationMemberRecord,
    OrganizationRecord,
    SessionCourseDayRecord,
    SessionTeacherRecord,
    UserRecord,
)
from app.schemas.academic import TeacherGradeEntry
from app.services.grades import grade_average_pct, save_teacher_grades, teacher_gradebook
from app.services.learning_progress import badge_for_enrollment, student_grades
from app.services.membership_roles import replace_effective_roles
from app.services.tenancy import resolve_tenant_context


def member(db, org, email, role):
    user = UserRecord(email=email, full_name=email.split("@")[0], status="active")
    db.add(user)
    db.flush()
    record = OrganizationMemberRecord(organization_id=org.id, user_id=user.id, role=role, status="active")
    db.add(record)
    db.flush()
    replace_effective_roles(db, record, {role})
    return user


def school(format_type="live", *, ended=False):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    db = Session(engine, expire_on_commit=False)
    org = OrganizationRecord(name="School", slug="school")
    db.add(org)
    db.flush()
    teacher = member(db, org, "teacher@school.test", "teacher")
    student = member(db, org, "student@school.test", "student")
    formation = FormationRecord(organization_id=org.id, slug="f", title="F", format_type=format_type)
    db.add(formation)
    db.flush()
    today = datetime.now(UTC).date()
    session = FormationSessionRecord(
        organization_id=org.id, formation_id=formation.id, label="Cohorte",
        start_date=today - timedelta(days=30),
        end_date=today - timedelta(days=2) if ended else today + timedelta(days=30),
        status="open",
    )
    db.add(session)
    db.flush()
    enrollment = EnrollmentRecord(organization_id=org.id, session_id=session.id, student_id=student.id, status="active")
    db.add_all([
        enrollment,
        SessionTeacherRecord(organization_id=org.id, session_id=session.id, teacher_id=teacher.id, role="principal"),
    ])
    db.commit()
    return db, org, teacher, student, session, enrollment


def tenant_for(db, org, user):
    return resolve_tenant_context(db, user=user, organization_id=org.id)


def course_day(db, org, session, teacher, *, days_from_now=-1, **values):
    day = SessionCourseDayRecord(
        organization_id=org.id, session_id=session.id, teacher_id=teacher.id, title="Séance",
        scheduled_at=datetime.now(UTC) + timedelta(days=days_from_now), duration_minutes=90, **values,
    )
    db.add(day)
    db.commit()
    return day


def entry(enrollment, day=None, **values):
    return TeacherGradeEntry(**{
        "enrollment_id": enrollment.id,
        "course_day_id": day.id if day else None,
        "label": "Évaluation",
        "score": 14,
        **values,
    })


def saved_grades(db):
    return db.scalars(select(GradeRecord)).all()


def test_course_day_grade_opens_once_the_day_is_over():
    db, org, teacher, student, session, enrollment = school()
    tenant = tenant_for(db, org, teacher)
    upcoming = course_day(db, org, session, teacher, days_from_now=1)
    with pytest.raises(HTTPException) as exc:
        save_teacher_grades(db, tenant, session.id, [entry(enrollment, upcoming)])
    assert exc.value.status_code == 409

    finished = course_day(db, org, session, teacher)
    gradebook = save_teacher_grades(db, tenant, session.id, [entry(enrollment, finished)])
    assert [(item.label, item.score, item.source_type, item.course_day_title) for item in gradebook.grades] == [
        ("Évaluation", 14, "manual", "Séance"),
    ]
    assert {item.id: item.can_grade for item in gradebook.course_days} == {upcoming.id: False, finished.id: True}
    assert [item.label for item in student_grades(db, tenant_for(db, org, student))] == ["Évaluation"]


def test_session_grade_waits_for_the_end_of_the_session():
    db, org, teacher, _student, session, enrollment = school()
    tenant = tenant_for(db, org, teacher)
    assert teacher_gradebook(db, tenant, session.id).can_grade_session is False
    with pytest.raises(HTTPException) as exc:
        save_teacher_grades(db, tenant, session.id, [entry(enrollment)])
    assert exc.value.status_code == 409
    assert "fin de la session" in exc.value.detail

    session.end_date = datetime.now(UTC).date() - timedelta(days=2)
    db.commit()
    gradebook = save_teacher_grades(db, tenant, session.id, [entry(enrollment)])
    assert gradebook.can_grade_session is True
    assert gradebook.grades[0].course_day_id is None


@pytest.mark.parametrize("values", [{"status": "cancelled"}, {"delivery_status": "not_held"}])
def test_session_that_did_not_take_place_cannot_be_graded(values):
    db, org, teacher, _student, session, enrollment = school()
    day = course_day(db, org, session, teacher, **values)
    with pytest.raises(HTTPException) as exc:
        save_teacher_grades(db, tenant_for(db, org, teacher), session.id, [entry(enrollment, day)])
    assert exc.value.status_code == 409


def test_interrupted_session_can_be_graded():
    db, org, teacher, _student, session, enrollment = school()
    day = course_day(db, org, session, teacher, delivery_status="interrupted")
    save_teacher_grades(db, tenant_for(db, org, teacher), session.id, [entry(enrollment, day)])
    assert len(saved_grades(db)) == 1


def test_teacher_only_grades_their_own_course_days():
    db, org, teacher, _student, session, enrollment = school()
    colleague = member(db, org, "colleague@school.test", "teacher")
    db.add(SessionTeacherRecord(organization_id=org.id, session_id=session.id, teacher_id=colleague.id, role="intervenant"))
    day = course_day(db, org, session, colleague)
    tenant = tenant_for(db, org, teacher)
    with pytest.raises(HTTPException) as exc:
        save_teacher_grades(db, tenant, session.id, [entry(enrollment, day)])
    assert exc.value.status_code == 403
    assert teacher_gradebook(db, tenant, session.id).course_days[0].can_grade is False


def test_teacher_must_be_assigned_to_the_session():
    db, org, _teacher, _student, session, enrollment = school()
    outsider = member(db, org, "outsider@school.test", "teacher")
    db.commit()
    tenant = tenant_for(db, org, outsider)
    for action in (
        lambda: teacher_gradebook(db, tenant, session.id),
        lambda: save_teacher_grades(db, tenant, session.id, [entry(enrollment)]),
    ):
        with pytest.raises(HTTPException) as exc:
            action()
        assert exc.value.status_code == 403


@pytest.mark.parametrize(
    "values, status_code",
    [({"score": 21}, 422), ({"label": "   "}, 422), ({"enrollment_id": 9999}, 422)],
)
def test_one_invalid_entry_saves_nothing(values, status_code):
    db, org, teacher, _student, session, enrollment = school()
    day = course_day(db, org, session, teacher)
    entries = [entry(enrollment, day, label="Valide"), entry(enrollment, day, **values)]
    with pytest.raises(HTTPException) as exc:
        save_teacher_grades(db, tenant_for(db, org, teacher), session.id, entries)
    assert exc.value.status_code == status_code
    assert saved_grades(db) == []


def test_saving_the_same_evaluation_again_updates_the_grade():
    db, org, teacher, _student, session, enrollment = school()
    day = course_day(db, org, session, teacher)
    tenant = tenant_for(db, org, teacher)
    save_teacher_grades(db, tenant, session.id, [entry(enrollment, day, score=10)])
    save_teacher_grades(db, tenant, session.id, [entry(enrollment, day, score=16, max_score=40, note="Bien")])
    [grade] = saved_grades(db)
    assert (grade.score, grade.max_score, grade.note) == (16, 40, "Bien")


def test_automatic_grade_with_the_same_label_is_left_alone():
    db, org, teacher, _student, session, enrollment = school()
    day = course_day(db, org, session, teacher)
    db.add(GradeRecord(
        organization_id=org.id, session_id=session.id, enrollment_id=enrollment.id, teacher_id=teacher.id,
        course_day_id=day.id, source_type="assignment", source_id=1, label="Évaluation", score=4, max_score=20,
    ))
    db.commit()
    save_teacher_grades(db, tenant_for(db, org, teacher), session.id, [entry(enrollment, day, score=18)])
    assert sorted(item.score for item in saved_grades(db)) == [4, 18]


def test_online_formations_have_no_teacher_grades():
    db, org, teacher, _student, session, enrollment = school("ligne", ended=True)
    with pytest.raises(HTTPException) as exc:
        save_teacher_grades(db, tenant_for(db, org, teacher), session.id, [entry(enrollment)])
    assert exc.value.status_code == 409


def test_support_mode_cannot_write_grades():
    db, org, teacher, _student, session, enrollment = school(ended=True)
    tenant = replace(tenant_for(db, org, teacher), support_mode=True)
    with pytest.raises(HTTPException) as exc:
        save_teacher_grades(db, tenant, session.id, [entry(enrollment)])
    assert exc.value.status_code == 403


def test_teacher_grades_feed_the_average_and_the_badge():
    db, org, teacher, student, session, enrollment = school(ended=True)
    tenant = tenant_for(db, org, teacher)
    save_teacher_grades(db, tenant, session.id, [entry(enrollment, score=8)])
    assert grade_average_pct(db, organization_id=org.id, enrollment_id=enrollment.id) == 40.0
    badge = badge_for_enrollment(db, tenant_for(db, org, student), enrollment)
    assert badge.grade_average_pct == 40.0
    assert badge.level == "debutant"
    assert "obtenez une moyenne d'au moins 10/20" in badge.missing_requirements


def test_grades_api_round_trip():
    db, org, teacher, _student, session, enrollment = school(ended=True)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_tenant_context] = lambda: tenant_for(db, org, teacher)
    try:
        client = TestClient(app)
        url = f"/api/v1/academic/teacher/sessions/{session.id}/grades"
        saved = client.put(url, json=[{"enrollment_id": enrollment.id, "label": "Projet", "score": 15}])
        refused = client.put(url, json=[{"enrollment_id": enrollment.id, "label": "Projet", "score": -1}])
        read = client.get(url)
    finally:
        app.dependency_overrides.clear()
    assert saved.status_code == 200
    assert refused.status_code == 422
    assert read.status_code == 200
    assert read.json()["can_grade_session"] is True
    assert [(item["label"], item["score"], item["max_score"]) for item in read.json()["grades"]] == [("Projet", 15, 20)]
