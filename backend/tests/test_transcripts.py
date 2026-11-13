"""The student's transcript (app/services/transcripts.py, transcript_pdf.py)."""
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from test_academic_suite import ctx, seed

from app.core.security import create_access_token
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.entities import (
    GradeRecord,
    OrganizationMemberRecord,
    OrganizationStudentProfileRecord,
    UserRecord,
)
from app.services.grades import grade_average_pct
from app.services.membership_roles import replace_effective_roles
from app.services.transcript_pdf import build_transcript_pdf
from app.services.transcripts import build_transcript, mention_for, my_transcripts, readable_enrollment


def shared_db() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return Session(engine, expire_on_commit=False)


def grade(db, enrollment, source_type, label, score, max_score=20, **extra):
    db.add(GradeRecord(organization_id=enrollment.organization_id, session_id=enrollment.session_id,
                       enrollment_id=enrollment.id, source_type=source_type, label=label,
                       score=score, max_score=max_score, **extra))


@pytest.fixture()
def school():
    db = shared_db()
    org, teacher, student, classmate, session, enrollment, classmate_enrollment, _lesson, day = seed(db)
    director = UserRecord(email="direction@test.dev", full_name="Direction", status="active")
    outsider = UserRecord(email="other.teacher@test.dev", full_name="Autre prof", status="active")
    db.add_all([director, outsider])
    db.flush()
    for user, role in ((director, "owner"), (outsider, "teacher")):
        member = OrganizationMemberRecord(organization_id=org.id, user_id=user.id, role=role, status="active")
        db.add(member)
        db.flush()
        replace_effective_roles(db, member, {role})
    db.add(OrganizationStudentProfileRecord(organization_id=org.id, user_id=student.id, student_code="SC-2025-0001", status="active"))
    grade(db, enrollment, "assignment", "TP : logo", 16, source_id=1)
    grade(db, enrollment, "quiz", "Quiz : couleurs", 4, 5, source_id=2)
    grade(db, enrollment, "quiz", "Examen : final", 12, source_id=3)
    grade(db, enrollment, "manual", "Participation", 15, course_day_id=day.id, note="Très investie")
    grade(db, enrollment, "manual", "Note globale", 36, 40)
    db.commit()
    yield db, org, teacher, student, classmate, director, outsider, enrollment, day
    db.close()


def test_the_transcript_groups_the_grades_and_gives_the_official_average(school):
    db, org, _teacher, student, *_rest, enrollment, day = school
    transcript = build_transcript(db, ctx(db, org, student), enrollment)

    assert [group.label for group in transcript.groups] == [
        "Travaux pratiques", "Examens", "Notes de séance", "Notes du professeur", "Quiz (hors moyenne)",
    ]
    quiz = transcript.groups[-1].lines[0]
    assert (quiz.score_20, quiz.counted) == (16, False)
    session_grade = transcript.groups[2].lines[0]
    assert (session_grade.date, session_grade.note) == (day.scheduled_at.date(), "Très investie")
    assert transcript.groups[3].lines[0].score_20 == 18  # 36/40

    # 16, 12, 15 and 18 count; the automatic quiz is left out, as for the badge.
    assert transcript.average_20 == 15.25 and transcript.mention == "Bien"
    assert abs(transcript.average_20 * 5 - grade_average_pct(db, organization_id=org.id, enrollment_id=enrollment.id)) < 0.1
    assert (transcript.student_code, transcript.session_label) == ("SC-2025-0001", "Accès en ligne")
    # An online formation stays provisional until the enrollment is completed.
    assert transcript.status == "provisional"
    enrollment.status = "completed"
    db.commit()
    assert build_transcript(db, ctx(db, org, student), enrollment).status == "final"


@pytest.mark.parametrize(("average", "mention"), [(None, None), (9.99, None), (10, "Passable"), (12, "Assez bien"), (14, "Bien"), (16, "Très bien")])
def test_mentions(average, mention):
    assert mention_for(average) == mention


def test_who_reads_a_transcript(school):
    db, org, teacher, student, classmate, director, outsider, enrollment, _day = school
    for reader in (student, teacher, director):
        assert readable_enrollment(db, ctx(db, org, reader), enrollment.id).id == enrollment.id
    for stranger in (classmate, outsider):
        with pytest.raises(HTTPException) as refused:
            readable_enrollment(db, ctx(db, org, stranger), enrollment.id)
        assert refused.value.status_code == 403
    with pytest.raises(HTTPException) as missing:
        readable_enrollment(db, ctx(db, org, director), 9999)
    assert missing.value.status_code == 404


def test_a_student_lists_their_own_transcripts(school):
    db, org, _teacher, student, classmate, *_rest = school
    mine = my_transcripts(db, ctx(db, org, student))
    assert [(item.formation_title, item.average_20) for item in mine] == [("Motion Design", 15.25)]
    assert my_transcripts(db, ctx(db, org, classmate))[0].average_20 is None


def test_the_transcript_downloads_as_a_pdf(school):
    db, org, _teacher, student, _classmate, director, _outsider, enrollment, _day = school
    filename, content = build_transcript_pdf(build_transcript(db, ctx(db, org, student), enrollment))
    assert content.startswith(b"%PDF") and filename == "releve-sc-2025-0001-motion-design.pdf"

    app.dependency_overrides[get_db] = lambda: db
    try:
        with TestClient(app) as client:
            for reader, expected in ((director, 200), (student, 200)):
                headers = {"Authorization": f"Bearer {create_access_token(reader.id, session_version=reader.session_version)}",
                           "X-Organization-Id": str(org.id)}
                response = client.get(f"/api/v1/transcripts/{enrollment.id}/pdf", headers=headers)
                assert response.status_code == expected, response.text
                assert response.headers["content-type"] == "application/pdf"
                assert 'filename="releve-' in response.headers["content-disposition"]
            screen = client.get(f"/api/v1/transcripts/{enrollment.id}", headers=headers).json()
            assert screen["average_20"] == 15.25 and screen["mention"] == "Bien"
    finally:
        app.dependency_overrides.clear()
