from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models.entities import (
    AssignmentRecord,
    AssignmentSubmissionRecord,
    ChapterRecord,
    CourseRecord,
    EnrollmentRecord,
    FormationRecord,
    FormationSessionRecord,
    GradeRecord,
    LessonRecord,
    OrganizationMemberRecord,
    OrganizationRecord,
    QuizAttemptRecord,
    QuizRecord,
    SessionCourseDayRecord,
    SessionTeacherRecord,
    UserRecord,
)
from app.services.badge_rules import (
    BadgeStats,
    badge_level,
    badge_ring_pct,
    badge_score,
    level_readiness_pct,
    missing_requirements,
)
from app.services.class_certificates import list_student_classes
from app.services.grades import grade_average_pct
from app.services.learning_progress import badge_for_enrollment
from app.services.membership_roles import replace_effective_roles
from app.services.tenancy import resolve_tenant_context

COMPLETE = BadgeStats(
    guided=True,
    format_type="live",
    total_lessons=10,
    completed_lessons=10,
    lesson_progress_pct=100.0,
    total_assignments=3,
    submitted_assignments=3,
    validated_assignments=3,
    total_quizzes=4,
    attempted_quizzes=4,
    passed_quizzes=4,
    attendance_total=10,
    attendance_present=10,
    grade_average_pct=None,
    has_final_project=False,
    final_project_validated=False,
    professional_eligible=True,
)


def test_complete_and_reviewed_path_reaches_professional():
    assert badge_level(COMPLETE) == "professionnel"


def test_lessons_alone_do_not_earn_a_level():
    stats = replace(COMPLETE, submitted_assignments=0, validated_assignments=0, attempted_quizzes=0, passed_quizzes=0)
    assert badge_score(stats) >= 25
    assert badge_level(stats) == "aventurier"


def test_unreviewed_assignments_stop_at_beginner():
    assert badge_level(replace(COMPLETE, validated_assignments=0)) == "debutant"


def test_session_must_be_over_for_professional():
    assert badge_level(replace(COMPLETE, professional_eligible=False)) == "semi_pro"


@pytest.mark.parametrize("average, level", [(79.9, "semi_pro"), (59.9, "intermediaire"), (49.9, "debutant")])
def test_grade_average_gates_each_level(average, level):
    assert badge_level(replace(COMPLETE, grade_average_pct=average)) == level


def test_final_project_only_gates_professional_on_guided_paths():
    without_final = replace(COMPLETE, professional_eligible=False)
    with_final = replace(without_final, has_final_project=True)
    assert badge_score(with_final) == badge_score(without_final)
    assert badge_level(with_final) == "semi_pro"
    assert badge_level(replace(COMPLETE, has_final_project=True)) == "semi_pro"
    assert badge_level(replace(COMPLETE, has_final_project=True, final_project_validated=True)) == "professionnel"


def test_classic_path_keeps_score_levels_and_final_project_in_score():
    stats = replace(
        COMPLETE, guided=False, format_type="ligne",
        attempted_quizzes=0, passed_quizzes=0, submitted_assignments=0, validated_assignments=0,
    )
    assert badge_level(stats) == "intermediaire"
    assert badge_score(replace(stats, has_final_project=True)) == badge_score(stats)
    reviewed = replace(stats, submitted_assignments=3, validated_assignments=3)
    assert badge_score(replace(reviewed, has_final_project=True)) < badge_score(reviewed)


def test_missing_requirements_explain_the_next_level():
    stats = replace(COMPLETE, validated_assignments=0, professional_eligible=False)
    assert missing_requirements("intermediaire", stats) == ["faites corriger et valider 2 TP sur 3"]


def test_readiness_averages_the_criteria_of_the_level():
    stats = replace(COMPLETE, validated_assignments=0)
    # Score, lessons, quizzes and attendance are met; assignments are not.
    assert level_readiness_pct("intermediaire", stats) == 80.0


def school(format_type="live"):
    engine = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    db = Session(engine, expire_on_commit=False)
    org = OrganizationRecord(name="School", slug="school")
    teacher = UserRecord(email="t@school.test", full_name="Teacher", status="active")
    student = UserRecord(email="s@school.test", full_name="Student", status="active")
    classmate = UserRecord(email="c@school.test", full_name="Classmate", status="active")
    db.add_all([org, teacher, student, classmate])
    db.flush()
    members = {
        user: OrganizationMemberRecord(organization_id=org.id, user_id=user.id, role=role, status="active")
        for user, role in ((teacher, "teacher"), (student, "student"), (classmate, "student"))
    }
    db.add_all(members.values())
    db.flush()
    for user, member in members.items():
        replace_effective_roles(db, member, {member.role})
    formation = FormationRecord(organization_id=org.id, slug="f", title="F", format_type=format_type)
    db.add(formation)
    db.flush()
    today = datetime.now(UTC).date()
    session = FormationSessionRecord(
        organization_id=org.id, formation_id=formation.id, label="Cohorte",
        start_date=today - timedelta(days=20), end_date=today + timedelta(days=20), status="open",
    )
    db.add(session)
    db.flush()
    enrollment = EnrollmentRecord(organization_id=org.id, session_id=session.id, student_id=student.id, status="active")
    db.add_all([
        enrollment,
        EnrollmentRecord(organization_id=org.id, session_id=session.id, student_id=classmate.id, status="active"),
        SessionTeacherRecord(organization_id=org.id, session_id=session.id, teacher_id=teacher.id, role="principal"),
    ])
    db.commit()
    return db, org, teacher, student, classmate, session, enrollment


def tenant_for(db, org, user):
    return resolve_tenant_context(db, user=user, organization_id=org.id)


def add_quiz(db, org, session, teacher, **values):
    quiz = QuizRecord(
        organization_id=org.id, session_id=session.id, teacher_id=teacher.id,
        title="Quiz", status="active", pass_pct=80, **values,
    )
    db.add(quiz)
    db.flush()
    return quiz


def add_assignment(db, org, session, teacher, **values):
    assignment = AssignmentRecord(
        organization_id=org.id, session_id=session.id, teacher_id=teacher.id, title="TP",
        due_date=datetime.now(UTC) + timedelta(days=5), **values,
    )
    db.add(assignment)
    db.flush()
    return assignment


def add_day(db, org, session, teacher, **values):
    day = SessionCourseDayRecord(
        organization_id=org.id, session_id=session.id, teacher_id=teacher.id, title="Séance",
        scheduled_at=datetime.now(UTC) - timedelta(days=2), duration_minutes=90, **values,
    )
    db.add(day)
    db.flush()
    return day


def add_lesson(db, org, session, teacher, **values):
    course = CourseRecord(organization_id=org.id, session_id=session.id, teacher_id=teacher.id, title="Cours", status="published")
    db.add(course)
    db.flush()
    chapter = ChapterRecord(organization_id=org.id, course_id=course.id, title="Chapitre")
    db.add(chapter)
    db.flush()
    lesson = LessonRecord(organization_id=org.id, chapter_id=chapter.id, title="Leçon", **values)
    db.add(lesson)
    db.flush()
    return lesson


def test_quiz_grades_stay_out_of_the_average_but_exams_count():
    db, org, _teacher, _student, _classmate, session, enrollment = school()
    db.add_all([
        GradeRecord(organization_id=org.id, session_id=session.id, enrollment_id=enrollment.id,
                    source_type="quiz", source_id=1, label="Quiz : Bases", score=20, max_score=20),
        GradeRecord(organization_id=org.id, session_id=session.id, enrollment_id=enrollment.id,
                    source_type="quiz", source_id=2, label="Examen : Final", score=10, max_score=20),
        GradeRecord(organization_id=org.id, session_id=session.id, enrollment_id=enrollment.id,
                    source_type="assignment", source_id=3, label="Devoir : TP", score=14, max_score=20),
    ])
    db.commit()
    assert grade_average_pct(db, organization_id=org.id, enrollment_id=enrollment.id) == 60.0


def test_badge_counts_reviewed_assignments_separately():
    db, org, teacher, student, _classmate, session, enrollment = school()
    assignment = add_assignment(db, org, session, teacher)
    submission = AssignmentSubmissionRecord(
        organization_id=org.id, assignment_id=assignment.id, enrollment_id=enrollment.id,
        file_url="https://example.test/tp.pdf", submitted_at=datetime.now(UTC),
    )
    db.add(submission)
    db.commit()
    tenant = tenant_for(db, org, student)
    unreviewed = badge_for_enrollment(db, tenant, enrollment)
    assert unreviewed.score_pct == 40.0
    assert unreviewed.assignment_progress_pct == 100

    submission.is_reviewed = True
    submission.review_score = 14
    db.commit()
    assert badge_for_enrollment(db, tenant, enrollment).score_pct == 100.0


def test_badge_ignores_quizzes_not_open_and_lesson_validation_quizzes():
    db, org, teacher, student, _classmate, session, enrollment = school()
    add_quiz(db, org, session, teacher, scheduled_at=datetime.now(UTC) + timedelta(days=5))
    validation_quiz = add_quiz(db, org, session, teacher)
    add_lesson(db, org, session, teacher, lesson_type="pdf", quiz_id=validation_quiz.id)
    counted = add_quiz(db, org, session, teacher)
    db.add(QuizAttemptRecord(
        organization_id=org.id, quiz_id=counted.id, enrollment_id=enrollment.id,
        attempt_number=1, answers=[], score_pct=90, submitted_at=datetime.now(UTC),
    ))
    db.commit()
    assert badge_for_enrollment(db, tenant_for(db, org, student), enrollment).quiz_progress_pct == 100


def test_work_of_a_session_not_held_does_not_block_the_badge():
    db, org, teacher, student, _classmate, session, enrollment = school()
    day = add_day(db, org, session, teacher, delivery_status="not_held", report_submitted_at=datetime.now(UTC))
    add_assignment(db, org, session, teacher, course_day_id=day.id)
    add_quiz(db, org, session, teacher, course_day_id=day.id)
    db.commit()
    badge = badge_for_enrollment(db, tenant_for(db, org, student), enrollment)
    assert badge.assignment_progress_pct is None
    assert badge.quiz_progress_pct is None


def test_every_final_project_must_be_validated():
    db, org, teacher, student, _classmate, session, enrollment = school()
    first = add_assignment(db, org, session, teacher, is_final_project=True)
    second = add_assignment(db, org, session, teacher, is_final_project=True)
    now = datetime.now(UTC)
    db.add(AssignmentSubmissionRecord(
        organization_id=org.id, assignment_id=first.id, enrollment_id=enrollment.id,
        file_url="https://example.test/a.pdf", submitted_at=now, is_reviewed=True, review_score=18,
    ))
    passing = AssignmentSubmissionRecord(
        organization_id=org.id, assignment_id=second.id, enrollment_id=enrollment.id,
        file_url="https://example.test/b.pdf", submitted_at=now, is_reviewed=True, review_score=12,
    )
    db.add(passing)
    db.commit()
    tenant = tenant_for(db, org, student)
    assert badge_for_enrollment(db, tenant, enrollment).final_project_validated is False
    passing.review_score = 16
    db.commit()
    assert badge_for_enrollment(db, tenant, enrollment).final_project_validated is True


def test_class_page_only_exposes_the_badge_of_classmates():
    db, org, teacher, student, classmate, session, _enrollment = school()
    add_assignment(db, org, session, teacher)
    db.add(GradeRecord(
        organization_id=org.id, session_id=session.id, enrollment_id=_enrollment.id,
        source_type="assignment", source_id=1, label="Devoir : TP", score=12, max_score=20,
    ))
    db.commit()
    classmates = list_student_classes(db, tenant_for(db, org, classmate))[0].classmates
    theirs = next(item for item in classmates if item.user_id == student.id)
    assert set(theirs.badge.model_dump()) == {"level", "label", "ring_pct"}
    assert theirs.badge.level == "aventurier"


@pytest.mark.parametrize("score, ring", [(60.0, 40.0), (74.9, 99.0)])
def test_classic_ring_follows_the_score_between_two_levels(score, ring):
    lessons = int(score * 10)
    stats = replace(
        COMPLETE, guided=False, format_type="ligne", total_lessons=1000, completed_lessons=lessons,
        lesson_progress_pct=score, total_assignments=0, submitted_assignments=0, validated_assignments=0,
        total_quizzes=0, attempted_quizzes=0, passed_quizzes=0, attendance_total=0, attendance_present=0,
    )
    assert badge_ring_pct("intermediaire", "semi_pro", stats) == ring


def test_guided_ring_never_reaches_a_full_circle_before_the_award():
    assert badge_ring_pct("semi_pro", "professionnel", replace(COMPLETE, professional_eligible=False)) < 100
    assert badge_ring_pct("professionnel", None, COMPLETE) == 100


def test_session_not_started_explains_the_empty_badge():
    db, org, _teacher, student, _classmate, session, enrollment = school()
    session.start_date = date.today() + timedelta(days=10)
    session.end_date = date.today() + timedelta(days=40)
    db.commit()
    badge = badge_for_enrollment(db, tenant_for(db, org, student), enrollment)
    assert badge.level == "aventurier"
    assert badge.missing_requirements == ["Session non démarrée"]
