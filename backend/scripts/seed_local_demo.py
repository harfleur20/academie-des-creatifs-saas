from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.entities import (
    ChapterRecord,
    CourseRecord,
    EnrollmentRecord,
    FormationRecord,
    FormationSessionRecord,
    LessonRecord,
    OrganizationMemberRecord,
    OrganizationRecord,
    SessionCourseDayRecord,
    SessionTeacherRecord,
    UserRecord,
)
from app.services.membership_roles import replace_effective_roles


TEACHER_EMAIL = "prof.demo@academie.local"
STUDENT_EMAIL = "etudiant.demo@academie.local"
DEMO_PASSWORD = "Demo2026!"
SCHOOL_SLUG = "ecole-demo-local"
FORMATION_SLUG = "motion-design-demo"
SESSION_LABEL = "Cohorte Démo Octobre 2026"


def get_or_create_user(db, *, email: str, full_name: str) -> UserRecord:
    user = db.scalar(select(UserRecord).where(UserRecord.email == email))
    if user is None:
        user = UserRecord(
            email=email,
            full_name=full_name,
            status="active",
            platform_role="user",
        )
        db.add(user)
        db.flush()
    user.full_name = full_name
    user.status = "active"
    user.password_hash = hash_password(DEMO_PASSWORD)
    return user


def ensure_member(db, *, organization_id: int, user_id: int, role: str) -> None:
    member = db.scalar(
        select(OrganizationMemberRecord).where(
            OrganizationMemberRecord.organization_id == organization_id,
            OrganizationMemberRecord.user_id == user_id,
        )
    )
    if member is None:
        member = OrganizationMemberRecord(
            organization_id=organization_id,
            user_id=user_id,
            role=role,
            status="active",
        )
        db.add(member)
        db.flush()
    else:
        member.role = role
        member.status = "active"
    replace_effective_roles(db, member, {role})


def main() -> None:
    if settings.environment == "production":
        raise SystemExit("Refusé : ce seed local ne peut pas s'exécuter en production.")

    db = SessionLocal()
    try:
        school = db.scalar(
            select(OrganizationRecord).where(OrganizationRecord.slug == SCHOOL_SLUG)
        )
        if school is None:
            school = OrganizationRecord(
                name="École Démo Créatifs",
                slug=SCHOOL_SLUG,
                status="active",
                is_active=True,
                contact_email="contact.demo@academie.local",
                timezone="Europe/Paris",
                locale="fr-FR",
                primary_color="#1F2559",
                secondary_color="#18A7A3",
                accent_color="#131735",
            )
            db.add(school)
            db.flush()

        teacher = get_or_create_user(
            db,
            email=TEACHER_EMAIL,
            full_name="Kamla Loïc",
        )
        student = get_or_create_user(
            db,
            email=STUDENT_EMAIL,
            full_name="Francis Kenne",
        )
        ensure_member(
            db,
            organization_id=school.id,
            user_id=teacher.id,
            role="teacher",
        )
        ensure_member(
            db,
            organization_id=school.id,
            user_id=student.id,
            role="student",
        )

        formation = db.scalar(
            select(FormationRecord).where(
                FormationRecord.organization_id == school.id,
                FormationRecord.slug == FORMATION_SLUG,
            )
        )
        if formation is None:
            formation = FormationRecord(
                organization_id=school.id,
                slug=FORMATION_SLUG,
                title="Apprendre le motion design par la pratique",
                description="Formation de démonstration pour tester les espaces professeur et étudiant.",
                category="Design",
                level="Intermédiaire",
                format_type="live",
                training_hours=40,
                status="published",
            )
            db.add(formation)
            db.flush()
        else:
            formation.status = "published"

        today = date.today()
        session = db.scalar(
            select(FormationSessionRecord).where(
                FormationSessionRecord.organization_id == school.id,
                FormationSessionRecord.formation_id == formation.id,
                FormationSessionRecord.label == SESSION_LABEL,
            )
        )
        if session is None:
            session = FormationSessionRecord(
                organization_id=school.id,
                formation_id=formation.id,
                label=SESSION_LABEL,
                start_date=today - timedelta(days=2),
                end_date=today + timedelta(days=45),
                campus_label="En ligne",
                seat_capacity=25,
                status="open",
            )
            db.add(session)
            db.flush()
        else:
            session.start_date = today - timedelta(days=2)
            session.end_date = today + timedelta(days=45)
            session.status = "open"

        teacher_link = db.scalar(
            select(SessionTeacherRecord).where(
                SessionTeacherRecord.organization_id == school.id,
                SessionTeacherRecord.session_id == session.id,
                SessionTeacherRecord.teacher_id == teacher.id,
            )
        )
        if teacher_link is None:
            db.add(
                SessionTeacherRecord(
                    organization_id=school.id,
                    session_id=session.id,
                    teacher_id=teacher.id,
                    role="principal",
                )
            )
        else:
            teacher_link.role = "principal"

        enrollment = db.scalar(
            select(EnrollmentRecord).where(
                EnrollmentRecord.organization_id == school.id,
                EnrollmentRecord.session_id == session.id,
                EnrollmentRecord.student_id == student.id,
            )
        )
        if enrollment is None:
            enrollment = EnrollmentRecord(
                organization_id=school.id,
                session_id=session.id,
                student_id=student.id,
                status="active",
            )
            db.add(enrollment)
        else:
            enrollment.status = "active"

        course = db.scalar(
            select(CourseRecord).where(
                CourseRecord.organization_id == school.id,
                CourseRecord.session_id == session.id,
                CourseRecord.title == "Cours de développement logiciel",
            )
        )
        if course is None:
            course = CourseRecord(
                organization_id=school.id,
                session_id=session.id,
                teacher_id=teacher.id,
                title="Cours de développement logiciel",
                description="Cours de démonstration.",
                status="published",
            )
            db.add(course)
            db.flush()
        else:
            course.teacher_id = teacher.id
            course.status = "published"

        chapter = db.scalar(
            select(ChapterRecord).where(
                ChapterRecord.organization_id == school.id,
                ChapterRecord.course_id == course.id,
                ChapterRecord.order_index == 0,
            )
        )
        if chapter is None:
            chapter = ChapterRecord(
                organization_id=school.id,
                course_id=course.id,
                title="Module 1 : Introduction",
                order_index=0,
            )
            db.add(chapter)
            db.flush()

        lesson = db.scalar(
            select(LessonRecord).where(
                LessonRecord.organization_id == school.id,
                LessonRecord.chapter_id == chapter.id,
                LessonRecord.order_index == 0,
            )
        )
        if lesson is None:
            db.add(
                LessonRecord(
                    organization_id=school.id,
                    chapter_id=chapter.id,
                    title="Bienvenue dans la formation",
                    order_index=0,
                    lesson_type="text",
                    content="Contenu de démonstration pour vérifier le lecteur étudiant.",
                )
            )

        next_course_at = datetime.now(UTC) + timedelta(days=1, hours=2)
        course_day = db.scalar(
            select(SessionCourseDayRecord).where(
                SessionCourseDayRecord.organization_id == school.id,
                SessionCourseDayRecord.session_id == session.id,
                SessionCourseDayRecord.title == "Journée de cours",
            )
        )
        if course_day is None:
            course_day = SessionCourseDayRecord(
                organization_id=school.id,
                session_id=session.id,
                teacher_id=teacher.id,
                title="Journée de cours",
                scheduled_at=next_course_at,
                duration_minutes=90,
                status="planned",
            )
            db.add(course_day)
        else:
            course_day.teacher_id = teacher.id
            course_day.scheduled_at = next_course_at
            course_day.duration_minutes = 90
            course_day.status = "planned"

        db.commit()

        print("")
        print("Seed local créé / actualisé.")
        print(f"École     : {school.name}")
        print(f"Professeur: {TEACHER_EMAIL}")
        print(f"Étudiant  : {STUDENT_EMAIL}")
        print(f"Mot de passe commun: {DEMO_PASSWORD}")
        print("")
        print("Connexion: http://localhost:3000/login")
    finally:
        db.close()


if __name__ == "__main__":
    main()
