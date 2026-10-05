from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.entities import (
    EnrollmentRecord, FormationRecord, FormationSessionRecord, OrganizationMemberRecord,
    OrganizationRecord, SchoolNotificationRecord, SessionTeacherRecord, UserRecord,
)
from app.services.school_messages import create_thread, get_thread, list_recipients, list_threads, send_message
from app.services.tenancy import resolve_tenant_context


def test_messaging_recipients_and_threads_stay_within_school_and_session():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as db:
        first = OrganizationRecord(name="First", slug="first", status="active", is_active=True)
        second = OrganizationRecord(name="Second", slug="second", status="active", is_active=True)
        manager = UserRecord(email="manager@example.test", full_name="Manager", status="active")
        teacher = UserRecord(email="teacher@example.test", full_name="Teacher", status="active")
        student = UserRecord(email="student@example.test", full_name="Student", status="active")
        classmate = UserRecord(email="classmate@example.test", full_name="Classmate", status="active")
        outsider = UserRecord(email="outsider@example.test", full_name="Outsider", status="active")
        db.add_all([first, second, manager, teacher, student, classmate, outsider])
        db.flush()
        for user, role in ((manager, "owner"), (teacher, "teacher"), (student, "student"),
                           (classmate, "student"), (outsider, "student")):
            db.add(OrganizationMemberRecord(organization_id=first.id, user_id=user.id, role=role, status="active"))
        db.add(OrganizationMemberRecord(organization_id=second.id, user_id=manager.id, role="owner", status="active"))
        formation = FormationRecord(organization_id=first.id, slug="design", title="Design", status="draft")
        db.add(formation)
        db.flush()
        cohort = FormationSessionRecord(organization_id=first.id, formation_id=formation.id, label="Cohort",
                                        start_date=date(2026, 10, 1), end_date=date(2026, 12, 1))
        db.add(cohort)
        db.flush()
        db.add(SessionTeacherRecord(organization_id=first.id, session_id=cohort.id, teacher_id=teacher.id))
        for learner in (student, classmate):
            db.add(EnrollmentRecord(organization_id=first.id, session_id=cohort.id,
                                    student_id=learner.id, status="active"))
        db.commit()

        student_tenant = resolve_tenant_context(db, user=student, organization_id=first.id)
        teacher_tenant = resolve_tenant_context(db, user=teacher, organization_id=first.id)
        classmate_tenant = resolve_tenant_context(db, user=classmate, organization_id=first.id)
        second_tenant = resolve_tenant_context(db, user=manager, organization_id=second.id)
        student_recipients = {item.id for item in list_recipients(db, student_tenant)}
        assert student_recipients == {manager.id, teacher.id, classmate.id}
        assert outsider.id not in student_recipients

        with pytest.raises(HTTPException) as invalid:
            create_thread(db, student_tenant, [outsider.id], "Hi", "Hello")
        assert invalid.value.status_code == 403

        thread = create_thread(db, student_tenant, [teacher.id], "Cours", "Une question")
        assert thread.unread_count == 0
        assert len(list_threads(db, teacher_tenant)) == 1
        assert list_threads(db, teacher_tenant)[0].unread_count == 1
        assert get_thread(db, teacher_tenant, thread.id).unread_count == 0
        assert send_message(db, teacher_tenant, thread.id, "Voici la réponse").body == "Voici la réponse"
        assert list_threads(db, student_tenant)[0].unread_count == 1
        with pytest.raises(HTTPException) as unrelated:
            get_thread(db, classmate_tenant, thread.id)
        assert unrelated.value.status_code == 404
        with pytest.raises(HTTPException) as other_school:
            get_thread(db, second_tenant, thread.id)
        assert other_school.value.status_code == 404
        assert db.scalar(select(SchoolNotificationRecord.id).where(
            SchoolNotificationRecord.organization_id == first.id,
            SchoolNotificationRecord.user_id == teacher.id,
        )) is not None
