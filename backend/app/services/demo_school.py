"""The demonstration school, Studio Kora (docs/DEMO.md).

Fictional people and data, built once by `scripts/create_demo_school.py`. Dates are
set from the day it is built: the cohorts are under way, classes are held up to that
day and planned after it, the next cohorts open in about two months. Every email ends
in `@studiokora.example`; passwords are random unless one is given (local tests).
Images are served by the frontend, from `frontend/public/demo/` (Unsplash photos, see
docs/DEMO.md), at the site's address: FRONTEND_URL unless another one is given.
"""
from __future__ import annotations

import random
import secrets
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import delete, select, text, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password
from app.models.entities import (
    AssignmentRecord,
    AssignmentSubmissionRecord,
    ChapterRecord,
    CommunicationOutboxRecord,
    CourseRecord,
    EnrollmentRecord,
    FormationRecord,
    FormationSessionRecord,
    GradeRecord,
    LessonRecord,
    LiveRollCallAnswerRecord,
    LiveRollCallRecord,
    LiveRoomPresenceRecord,
    OrderInstallmentRecord,
    OrganizationLegalProfileRecord,
    OrganizationMemberRecord,
    OrganizationPublicSiteRecord,
    OrganizationRecord,
    OrganizationStudentProfileRecord,
    PlanRecord,
    QuizAttemptRecord,
    QuizQuestionRecord,
    QuizRecord,
    SessionCourseDayRecord,
    SessionTeacherRecord,
    StudentOrderRecord,
    SubscriptionRecord,
    UserRecord,
)
from app.models.teacher_onboarding import OrganizationCharterRecord, TeacherProfessionalProfileRecord
from app.schemas.academic import AttendanceMarkPayload
from app.schemas.assignments import ReviewSubmission
from app.schemas.planning import CourseDayReportSubmit
from app.services.assignments import review_submission
from app.services.learning_progress import mark_attendance, mark_lesson_complete
from app.services.membership_roles import replace_effective_roles
from app.services.planning import submit_course_day_report
from app.services.school_branding import get_or_create_identity_records
from app.services.school_revenue import record_sale
from app.services.tenancy import resolve_tenant_context

DEMO_SLUG = "studio-kora"
EMAIL_DOMAIN = "studiokora.example"
ASSETS_PATH = "/demo"  # frontend/public/demo, served by the frontend at FRONTEND_URL
MONTHS = ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre")

TEACHERS = {
    "Kamla Loïc": ("Directeur artistique", ["design", "motion"], ["Illustrator", "After Effects"]),
    "Sandrine Ngo Bassa": ("Designer UI/UX", ["design", "marketing"], ["Figma", "Meta Ads"]),
    "Patrick Eboa": ("Photographe et monteur", ["photo", "video"], ["Lightroom", "Premiere Pro"]),
}
STUDENTS = (
    "Grâce Ndzana", "Junior Essomba", "Mireille Tchoupo", "Yannick Fotso", "Brenda Ewane", "Cédric Nana",
    "Laure Mvondo", "Steve Kamga", "Nadège Ekotto", "Boris Tagne", "Estelle Biyong", "Hervé Ndjock",
    "Carine Abena", "Rodrigue Mbia", "Sorelle Djomo", "Arnaud Nkeng", "Ingrid Moukouri", "Paul-Henri Ateba",
    "Vanessa Ngono", "Kevin Tchinda", "Rita Fouda", "Dimitri Owona", "Joëlle Etoundi", "Franck Noubissi",
    "Prisca Manga", "Alain Kouam",
)


@dataclass(frozen=True)
class DemoFormation:
    slug: str
    title: str
    category: str
    format_type: str  # live, ligne (online, at one's pace), presentiel
    hours: int
    price: int  # XAF, whole francs
    teacher: str
    start_offset: int  # days from the build day; the current cohort started then
    weeks: int
    students: int
    description: str


FORMATIONS = (
    DemoFormation("design-graphique", "Design graphique : les fondamentaux", "Design", "live", 90, 150_000, "Kamla Loïc", -37, 22, 14,
                  "Couleur, typographie, composition, identité visuelle : les bases solides pour créer des visuels qui marquent."),
    DemoFormation("motion-design", "Motion design avec After Effects", "Animation", "live", 72, 180_000, "Kamla Loïc", -10, 18, 9,
                  "Animez logos, textes et illustrations pour les réseaux sociaux et la publicité."),
    DemoFormation("ui-ux-design", "UI/UX design : de l'idée à la maquette", "Design", "ligne", 36, 120_000, "Sandrine Ngo Bassa", -60, 52, 10,
                  "Recherche utilisateur, wireframes et maquettes Figma pour des applications simples à utiliser."),
    DemoFormation("photographie", "Photographie et retouche", "Photo", "presentiel", 64, 200_000, "Patrick Eboa", -24, 16, 8,
                  "Lumière, cadrage et retouche : des ateliers pratiques en studio à Douala."),
    DemoFormation("marketing-digital", "Marketing digital et réseaux sociaux", "Marketing", "live", 48, 100_000, "Sandrine Ngo Bassa", -17, 12, 11,
                  "Stratégie de contenu, publicité Facebook et Instagram, mesure des résultats."),
    DemoFormation("montage-video", "Montage vidéo avec Premiere Pro", "Vidéo", "ligne", 30, 90_000, "Patrick Eboa", -45, 52, 7,
                  "Du rush au film fini : rythme, son, étalonnage et export pour le web."),
)
FEATURED = {"design-graphique", "motion-design", "ui-ux-design"}
MODULES = {
    "design-graphique": (("Les bases du design", ("Couleurs et contrastes", "Typographie", "Composition")),
                         ("Identité visuelle", ("Créer un logo", "La charte graphique")),
                         ("Print et réseaux sociaux", ("Affiche événementielle", "Visuels pour les réseaux"))),
}
DEFAULT_MODULES = (("Prise en main", ("Bienvenue", "Les outils", "Premier projet")),)
CLASS_TITLES = (
    "Couleurs et contrastes", "Typographie : choisir et associer", "Composition et grilles", "Atelier : affiche",
    "Créer un logo", "Logo : retours et itérations", "La charte graphique", "Atelier : charte",
    "Affiche événementielle", "Visuels pour les réseaux", "Revue de portfolio", "Atelier libre",
    "Questions-réponses", "Projet final : lancement", "Projet final : suivi", "Projet final : présentation",
)
LATE_ORDERS = 2  # a couple of late payments, for the follow-up screens

# Portraits: free Unsplash photos in frontend/public/demo/people (credits in docs/DEMO.md).
FEMALE_STUDENTS = frozenset({
    "Grâce Ndzana", "Mireille Tchoupo", "Brenda Ewane", "Laure Mvondo", "Nadège Ekotto", "Estelle Biyong",
    "Carine Abena", "Sorelle Djomo", "Ingrid Moukouri", "Vanessa Ngono", "Rita Fouda", "Joëlle Etoundi", "Prisca Manga",
})
STUDENT_PORTRAITS = {
    "f": ("f16", "f01", "f02", "f05", "f12", "f13", "f14", "f15", "f17", "f18", "f22"),
    "m": ("m14", "m02", "m03", "m06", "m11", "m12", "m13", "m16", "m20", "m21"),
}
PORTRAIT_SHARE = 0.8
TEACHER_PORTRAITS = {"Kamla Loïc": "m15", "Sandrine Ngo Bassa": "f06", "Patrick Eboa": "m23"}
OWNER_PORTRAIT = "f03"


def email_of(full_name: str) -> str:
    table = str.maketrans("àâäéèêëîïôöùûüçÀÂÉÈÊÎÔÙÛÇ", "aaaeeeeiioouuucAAEEEIOUUC")
    first, *rest = full_name.translate(table).lower().replace("-", "").split()
    return f"{first}.{''.join(rest)}@{EMAIL_DOMAIN}"


def month_label(day: date) -> str:
    return f"{MONTHS[day.month - 1]} {day.year}"


def remove_demo_school(db: Session, slug: str = DEMO_SLUG) -> bool:
    """Delete the demo school, everything it owns (database cascades) and its fictional people."""
    if db.get_bind().dialect.name == "sqlite":
        db.execute(text("PRAGMA foreign_keys=ON"))  # SQLite only cascades with it, before any write
    org = db.scalar(select(OrganizationRecord).where(OrganizationRecord.slug == slug))
    if org is None:
        return False
    # Orders hold on to their formation and session (RESTRICT): they go first.
    db.execute(delete(StudentOrderRecord).where(StudentOrderRecord.organization_id == org.id))
    db.execute(delete(OrganizationRecord).where(OrganizationRecord.id == org.id))
    db.execute(delete(UserRecord).where(UserRecord.email.like(f"%@{EMAIL_DOMAIN}")))
    db.commit()
    db.expunge_all()
    return True


class _Builder:
    def __init__(self, db: Session, *, slug: str, password: str | None, now: datetime, site_url: str):
        self.db = db
        self.slug = slug
        # Published covers must be full http(s) addresses (app/services/publication.py).
        self.assets = f"{site_url.rstrip('/')}{ASSETS_PATH}"
        # Without a given password, nobody knows it: the demo opens with a token (app/services/demo.py).
        self.password_hash = hash_password(password or secrets.token_urlsafe(32))
        self.now = now
        self.today = now.date()
        self.rng = random.Random(2026)

    # --- people ------------------------------------------------------------------------------
    def user(self, full_name: str) -> UserRecord:
        row = UserRecord(email=email_of(full_name), full_name=full_name, status="active", platform_role="user")
        row.password_hash = self.password_hash
        self.db.add(row)
        self.db.flush()
        return row

    def member(self, row: UserRecord, role: str) -> None:
        item = OrganizationMemberRecord(organization_id=self.org.id, user_id=row.id, role=role, status="active")
        self.db.add(item)
        self.db.flush()
        replace_effective_roles(self.db, item, {role})

    def ctx(self, row: UserRecord):
        return resolve_tenant_context(self.db, user=row, organization_id=self.org.id)

    # --- the school --------------------------------------------------------------------------
    def school(self) -> None:
        db, now = self.db, self.now
        self.next_start = self.today + timedelta(days=45)
        self.next_start += timedelta(days=(7 - self.next_start.weekday()) % 7)  # a Monday
        self.org = OrganizationRecord(
            name="Studio Kora", slug=self.slug, subdomain=self.slug, status="active", is_active=True,
            contact_email=f"contact@{EMAIL_DOMAIN}", timezone="Africa/Douala", locale="fr-FR",
            logo_url=f"{self.assets}/logo-kora.png", primary_color="#222A68", secondary_color="#0B8A83", accent_color="#131735",
        )
        db.add(self.org)
        db.flush()
        org_id = self.org.id
        db.add(OrganizationPublicSiteRecord(
            organization_id=org_id, site_name="Studio Kora", tagline="École des métiers créatifs à Douala",
            seo_description="Design graphique, motion, UI/UX, photo et vidéo : des formations en live, en ligne et en présentiel.",
            favicon_url=f"{self.assets}/logo-kora.png", hero_image_url=f"{self.assets}/hero.jpg",
            hero_title="Apprenez les métiers créatifs avec des pros",
            hero_subtitle="Design graphique, motion design, UI/UX, photo, vidéo : des formations en live, en ligne et à Douala, avec un suivi personnel jusqu'au certificat.",
            hero_cta_label="Voir les formations",
            announcement_enabled=True,
            announcement_text=f"Inscriptions ouvertes pour la cohorte de {month_label(self.next_start)} : paiement en 3 fois possible.",
            announcement_background_color="#FFF4E7", announcement_text_color="#7C4200",
            about_title="Une école à taille humaine",
            about_text="Studio Kora forme des designers, des monteurs et des photographes depuis Douala. Des promotions de 15 étudiants, des professionnels en activité comme professeurs, et des projets réels à chaque module.",
            contact_phone="+237 600 000 000", contact_email=f"contact@{EMAIL_DOMAIN}", contact_address="Bonapriso, Douala",
            social_links={}, footer_text="Studio Kora, école des métiers créatifs.",
            legal_notice="Studio Kora, école de formation professionnelle, Douala (démonstration).",
            sales_terms="Conditions générales de vente de démonstration.",
            privacy_policy="Politique de confidentialité de démonstration.",
            refund_policy="Politique de remboursement de démonstration.",
            font_heading="Inter", font_body="Inter", font_size_scale=110,
            student_code_prefix="SK", student_code_prefix_confirmed_at=now, is_published=True,
        ))
        db.add(OrganizationLegalProfileRecord(
            organization_id=org_id, legal_name="Studio Kora SARL (démonstration)", legal_address="Bonapriso, Douala, Cameroun",
            invoice_email=f"factures@{EMAIL_DOMAIN}", default_currency="XAF",
        ))
        db.flush()
        # Every identity record (site, legal, messages, certificates) exists from the start: a
        # demo request never keeps what it writes (app/api/dependencies.py).
        get_or_create_identity_records(db, self.org)
        for audience in ("teacher", "student"):
            db.add(OrganizationCharterRecord(organization_id=org_id, audience=audience, title="Charte", content="Charte de l'école.", is_enabled=False))

        self.owner = self.user("Aïcha Mbarga")
        self.owner.avatar_url = self.portrait(OWNER_PORTRAIT)
        self.member(self.owner, "owner")
        plan = db.scalar(select(PlanRecord).where(PlanRecord.code == "pro"))
        if plan is not None:
            db.add(SubscriptionRecord(
                organization_id=org_id, plan_id=plan.id, status="active", billing_interval="monthly",
                started_at=now - timedelta(days=75), current_period_start=now - timedelta(days=15),
                current_period_end=now + timedelta(days=15), provider="demo",
            ))

        self.teachers: dict[str, UserRecord] = {}
        for name, (title, domains, skills) in TEACHERS.items():
            row = self.user(name)
            row.avatar_url = self.portrait(TEACHER_PORTRAITS[name])
            self.member(row, "teacher")
            db.add(TeacherProfessionalProfileRecord(
                organization_id=org_id, user_id=row.id, professional_title=title, experience_years=8,
                activity_domains=domains, bio=f"{title} en activité, professeur à Studio Kora.", skills=skills,
                languages=["fr"], whatsapp_phone="+237600000000", whatsapp_country="CM", city="Douala", country="Cameroun",
                portfolio_url=f"https://{EMAIL_DOMAIN}/portfolio", profile_completed_at=now - timedelta(days=60),
            ))
            self.teachers[name] = row

        self.students: list[UserRecord] = []
        for index, name in enumerate(STUDENTS):
            row = self.user(name)
            self.member(row, "student")
            db.add(OrganizationStudentProfileRecord(
                organization_id=org_id, user_id=row.id, student_code=f"SK-{self.today.year}-{index + 1:04d}", status="active",
                first_purchase_at=now - timedelta(days=self.rng.randint(20, 70)),
            ))
            self.students.append(row)
        # How assiduous each student is: most follow, a few fall behind. Grâce, the student shown, follows.
        self.assiduity = {row.id: self.rng.choice((0.97, 0.95, 0.9, 0.9, 0.85, 0.8, 0.7, 0.55)) for row in self.students}
        self.assiduity[self.students[0].id] = 0.97
        db.commit()

    # --- formations, cohorts, orders ---------------------------------------------------------
    def formations(self) -> None:
        db, org_id = self.db, self.org.id
        self.cohorts: dict[str, tuple] = {}
        self.late_orders = 0
        self.late_students: set[int] = set()
        for item in FORMATIONS:
            formation = FormationRecord(
                organization_id=org_id, slug=item.slug, title=item.title, category=item.category, level="Débutant à intermédiaire",
                format_type=item.format_type, training_hours=item.hours, short_description=item.description, description=item.description,
                cover_image_url=f"{self.assets}/covers/{item.slug}.jpg",
                objectives="Réaliser des projets concrets pour votre portfolio.\nMaîtriser les outils des professionnels.",
                prerequisites="Un ordinateur et l'envie d'apprendre.",
                public_program="Module 1 : les bases\nModule 2 : la pratique\nModule 3 : le projet final",
                price_cents=item.price, currency="XAF", allow_installments=True, installment_count=3,
                reservation_deposit_enabled=item.format_type == "live",
                is_featured=item.slug in FEATURED, status="published",
            )
            db.add(formation)
            db.flush()
            start = self.today + timedelta(days=item.start_offset)
            online = item.format_type == "ligne"
            campus = "Douala, Bonapriso" if item.format_type == "presentiel" else "En ligne"
            session = self.session(formation, "Accès continu" if online else f"Cohorte {month_label(start)}", start, item.weeks, campus, item.teacher)
            if not online:
                self.session(formation, f"Cohorte {month_label(self.next_start)}", self.next_start, item.weeks, campus, item.teacher)
            others = self.students[1:]
            roster = [self.students[0], *self.rng.sample(others, item.students - 1)] if item.slug == "design-graphique" else self.rng.sample(others, item.students)
            enrollments = [self.enroll(formation, session, row, item) for row in roster]
            self.cohorts[item.slug] = (formation, session, self.teachers[item.teacher], enrollments, item.format_type, start)
        db.commit()

    def session(self, formation, label, start, weeks, campus, teacher_name) -> FormationSessionRecord:
        session = FormationSessionRecord(
            organization_id=self.org.id, formation_id=formation.id, label=label, start_date=start,
            end_date=start + timedelta(weeks=weeks), campus_label=campus, seat_capacity=16, status="open",
        )
        self.db.add(session)
        self.db.flush()
        self.db.add(SessionTeacherRecord(organization_id=self.org.id, session_id=session.id, teacher_id=self.teachers[teacher_name].id, role="principal"))
        return session

    def enroll(self, formation, session, row, item: DemoFormation) -> EnrollmentRecord:
        db, org_id, rng, now = self.db, self.org.id, self.rng, self.now
        enrollment = EnrollmentRecord(organization_id=org_id, session_id=session.id, student_id=row.id, status="active")
        db.add(enrollment)
        db.flush()
        # The order behind it: most paid in full, others in 3 instalments, a couple late.
        roll = rng.random()
        total = item.price
        full = roll < 0.55
        bought = now - timedelta(days=rng.randint(abs(item.start_offset) + 3, abs(item.start_offset) + 25))
        order = StudentOrderRecord(
            organization_id=org_id, order_number=f"SK-{session.id:02d}{enrollment.id:04d}", user_id=row.id,
            formation_id=formation.id, session_id=session.id, base_price_cents=total, final_price_cents=total,
            currency="XAF", payment_mode="full" if full else "installments", installment_count=1 if full else 3,
            payment_provider="taramoney", access_status="active", branding_snapshot={},
        )
        db.add(order)
        db.flush()
        if full:
            order.status, order.paid_cents, order.paid_at = "paid", total, bought
            db.add(OrderInstallmentRecord(organization_id=org_id, order_id=order.id, sequence=1, amount_cents=total,
                                          due_at=bought, grace_until=bought + timedelta(days=3), status="paid", paid_at=bought))
            return enrollment
        part = total // 3
        paid_parts = 3 if roll > 0.9 else 2 if roll > 0.7 else 1
        late = roll < 0.62 and paid_parts == 1 and self.late_orders < LATE_ORDERS and bought + timedelta(days=30) < now
        self.late_orders += late
        if late:
            self.late_students.add(row.id)
        for sequence in (1, 2, 3):
            due = bought + timedelta(days=30 * (sequence - 1))
            status = "paid" if sequence <= paid_parts else ("late" if late and due < now else "pending")
            db.add(OrderInstallmentRecord(organization_id=org_id, order_id=order.id, sequence=sequence,
                                          amount_cents=part if sequence < 3 else total - 2 * part, due_at=due,
                                          grace_until=due + timedelta(days=5), status=status,
                                          paid_at=due if status == "paid" else None))
        order.paid_cents = part * paid_parts if paid_parts < 3 else total
        order.status = "paid" if paid_parts == 3 else ("late" if late else "partially_paid")
        order.paid_at = bought if paid_parts == 3 else None
        return enrollment

    def ledger(self) -> None:
        """The school's sales, net of the platform commission, as if paid through the platform."""
        db = self.db
        for installment in db.scalars(select(OrderInstallmentRecord).where(
            OrderInstallmentRecord.organization_id == self.org.id, OrderInstallmentRecord.status == "paid",
        ).order_by(OrderInstallmentRecord.paid_at)):
            record_sale(db, self.org, db.get(StudentOrderRecord, installment.order_id), installment, installment.paid_at)
        db.commit()

    # --- teaching ----------------------------------------------------------------------------
    def courses(self) -> None:
        db, org_id = self.db, self.org.id
        self.lessons: dict[str, list[LessonRecord]] = {}
        for slug, (formation, session, teacher, *_rest) in self.cohorts.items():
            course = CourseRecord(organization_id=org_id, session_id=session.id, teacher_id=teacher.id, title=formation.title, status="published")
            db.add(course)
            db.flush()
            lessons = []
            for chapter_index, (chapter_title, lesson_titles) in enumerate(MODULES.get(slug, DEFAULT_MODULES)):
                chapter = ChapterRecord(organization_id=org_id, course_id=course.id, title=f"Module {chapter_index + 1} : {chapter_title}", order_index=chapter_index)
                db.add(chapter)
                db.flush()
                for lesson_index, lesson_title in enumerate(lesson_titles):
                    lesson = LessonRecord(organization_id=org_id, chapter_id=chapter.id, title=lesson_title, order_index=lesson_index,
                                          lesson_type="text", content=f"{lesson_title} : notions clés, exemples et exercice guidé.")
                    db.add(lesson)
                    db.flush()
                    lessons.append(lesson)
            self.lessons[slug] = lessons
        db.commit()

    def classes(self) -> None:
        """Tuesday and Thursday, 18:00 in Douala. Held classes have their presences and their report."""
        db, org_id, rng, now = self.db, self.org.id, self.rng, self.now
        for formation, session, teacher, enrollments, fmt, start in self.cohorts.values():
            if fmt == "ligne":
                continue
            teacher_ctx = self.ctx(teacher)
            cursor, days = start, []
            while cursor <= session.end_date:
                if cursor.weekday() in (1, 3):
                    days.append(datetime.combine(cursor, time(17, 0), tzinfo=UTC))
                cursor += timedelta(days=1)
            for index, scheduled in enumerate(days):
                day = SessionCourseDayRecord(organization_id=org_id, session_id=session.id, teacher_id=teacher.id,
                                             title=CLASS_TITLES[index % len(CLASS_TITLES)], scheduled_at=scheduled,
                                             duration_minutes=120, status="planned")
                db.add(day)
                db.flush()
                end = scheduled + timedelta(minutes=120)
                if end > now:
                    continue
                if fmt == "live":
                    day.started_at = scheduled - timedelta(minutes=3)
                    roll = LiveRollCallRecord(organization_id=org_id, course_day_id=day.id, started_by_user_id=teacher.id,
                                              started_at=scheduled + timedelta(minutes=40), closes_at=scheduled + timedelta(minutes=42))
                    db.add(roll)
                    db.flush()
                    for enrollment in enrollments:
                        if rng.random() > self.assiduity[enrollment.student_id]:
                            continue
                        late_by = rng.choice((0, 0, 0, 2, 5, 25))
                        stay = rng.randint(85, 120) - late_by
                        db.add(LiveRoomPresenceRecord(
                            organization_id=org_id, course_day_id=day.id, user_id=enrollment.student_id,
                            device_id=f"web-{enrollment.student_id}", device_label="Chrome · Windows",
                            first_joined_at=scheduled + timedelta(minutes=late_by),
                            last_seen_at=scheduled + timedelta(minutes=late_by + stay),
                            left_at=scheduled + timedelta(minutes=late_by + stay), seconds_in_room=stay * 60,
                        ))
                        db.add(LiveRollCallAnswerRecord(organization_id=org_id, roll_call_id=roll.id, user_id=enrollment.student_id,
                                                        answered_at=roll.started_at + timedelta(seconds=rng.randint(5, 80))))
                    db.commit()
                else:
                    for enrollment in enrollments:
                        if rng.random() <= self.assiduity[enrollment.student_id]:
                            mark_attendance(db, teacher_ctx, day.id, AttendanceMarkPayload(enrollment_id=enrollment.id, status="present"))
                submit_course_day_report(db, teacher_ctx, day.id, CourseDayReportSubmit(
                    delivery_status="held",
                    summary=f"{day.title} : notions vues, exercices en classe et corrections collectives.",
                    homework="Terminer l'exercice et le déposer avant la prochaine séance.",
                ), now=end + timedelta(minutes=30))
        db.commit()

    def progress(self) -> None:
        db, rng = self.db, self.rng
        for slug, (_formation, _session, _teacher, enrollments, _fmt, _start) in self.cohorts.items():
            lessons = self.lessons[slug]
            for enrollment in enrollments:
                student = db.get(UserRecord, enrollment.student_id)
                done = 5 if student.id == self.students[0].id else round(len(lessons) * min(1.0, self.assiduity[student.id] * rng.uniform(0.55, 1.0)))
                student_ctx = self.ctx(student)
                for lesson in lessons[:done]:
                    mark_lesson_complete(db, student_ctx, lesson.id)

    def evaluations(self) -> None:
        """Quizzes and practical works for the design cohort, the one Grâce follows."""
        db, org_id, rng, now = self.db, self.org.id, self.rng, self.now
        _formation, session, teacher, enrollments, _fmt, _start = self.cohorts["design-graphique"]
        grace = self.students[0].id
        quizzes = (("Couleurs et contrastes", 30, "closed", "quiz"), ("Examen de mi-parcours", 9, "closed", "exam"),
                   ("Typographie", 15, "active", "quiz"), ("Composition", 3, "active", "quiz"))
        for title, opened_days_ago, status, kind in quizzes:
            quiz = QuizRecord(organization_id=org_id, session_id=session.id, teacher_id=teacher.id, title=title, assessment_type=kind,
                              status=status, opened_at=now - timedelta(days=opened_days_ago), duration_minutes=15)
            db.add(quiz)
            db.flush()
            for number in range(5):
                db.add(QuizQuestionRecord(organization_id=org_id, quiz_id=quiz.id, order_index=number, text=f"Question {number + 1} sur {title.lower()}",
                                          options=["Réponse A", "Réponse B", "Réponse C", "Réponse D"], correct_index=number % 4))
            for enrollment in enrollments:
                if opened_days_ago < 7 and enrollment.student_id != grace and rng.random() < 0.6:
                    continue
                if rng.random() > self.assiduity[enrollment.student_id]:
                    continue
                if kind == "exam":
                    score = 75 if enrollment.student_id == grace else rng.choice((45, 55, 60, 65, 70, 80, 85))
                else:
                    score = 100 if enrollment.student_id == grace else rng.choice((60, 80, 80, 100, 100, 40))
                submitted = now - timedelta(days=max(0, opened_days_ago - 2), hours=rng.randint(1, 20))
                db.add(QuizAttemptRecord(organization_id=org_id, quiz_id=quiz.id, enrollment_id=enrollment.id, attempt_number=1,
                                         answers=[0, 1, 2, 3, 0], score_pct=score, submitted_at=submitted))
                self.grade(enrollment, source_type="quiz", source_id=quiz.id, when=submitted, score=round(score / 5, 2),
                           label=("Examen : " if kind == "exam" else "Quiz : ") + title,
                           note="Note automatique calculée depuis le meilleur score.", teacher_id=teacher.id)
        db.commit()

        teacher_ctx = self.ctx(teacher)
        for title, due_offset in (("Affiche typographique", -18), ("Logo pour une marque locale", -4), ("Charte graphique complète", 10)):
            work = AssignmentRecord(organization_id=org_id, session_id=session.id, teacher_id=teacher.id, title=title,
                                    publication_status="published", instructions=f"{title} : consignes détaillées dans la fiche.",
                                    due_date=now + timedelta(days=due_offset))
            db.add(work)
            db.flush()
            if due_offset > 0:
                continue
            for enrollment in enrollments:
                if rng.random() > self.assiduity[enrollment.student_id] and enrollment.student_id != grace:
                    continue
                submission = AssignmentSubmissionRecord(organization_id=org_id, assignment_id=work.id, enrollment_id=enrollment.id,
                                                        file_url=f"{self.assets}/covers/design-graphique.jpg",
                                                        submitted_at=now + timedelta(days=due_offset - rng.randint(0, 3)))
                db.add(submission)
                db.flush()
                if due_offset < -10 or rng.random() < 0.5:
                    db.commit()
                    score = 16 if enrollment.student_id == grace else rng.choice((11, 12, 13, 14, 15, 16, 17))
                    review_submission(db, teacher_ctx, work.id, submission.id, ReviewSubmission(review_score=score))
                    reviewed = submission.submitted_at + timedelta(days=2)
                    db.execute(update(GradeRecord).where(
                        GradeRecord.enrollment_id == enrollment.id, GradeRecord.source_type == "assignment",
                        GradeRecord.source_id == work.id,
                    ).values(created_at=reviewed, updated_at=reviewed))
        db.commit()

        # The teacher grades the workshops already held, as from the "Notes" page.
        workshops = db.scalars(select(SessionCourseDayRecord).where(
            SessionCourseDayRecord.session_id == session.id, SessionCourseDayRecord.report_submitted_at.is_not(None),
            SessionCourseDayRecord.title.like("Atelier%"),
        ).order_by(SessionCourseDayRecord.scheduled_at)).all()
        remarks = ("Bonne maîtrise des outils.", "Composition à aérer.", "Très bon sens du détail.", "Peut aller plus loin.", "")
        for day in workshops:
            for enrollment in enrollments:
                if rng.random() > self.assiduity[enrollment.student_id] and enrollment.student_id != grace:
                    continue
                score = 15 if enrollment.student_id == grace else rng.choice((10, 11, 12, 13, 14, 15, 16, 17))
                self.grade(enrollment, source_type="manual", source_id=None, when=day.scheduled_at + timedelta(hours=3),
                           score=score, label=day.title, note=rng.choice(remarks), teacher_id=teacher.id, course_day_id=day.id)
        db.commit()

    def grade(self, enrollment, *, source_type: str, source_id: int | None, when: datetime, score: float, label: str,
              note: str, teacher_id: int, course_day_id: int | None = None) -> None:
        self.db.add(GradeRecord(
            organization_id=self.org.id, session_id=enrollment.session_id, enrollment_id=enrollment.id,
            course_day_id=course_day_id, teacher_id=teacher_id, source_type=source_type, source_id=source_id,
            label=label, score=score, max_score=20, note=note, created_at=when, updated_at=when,
        ))

    def portrait(self, code: str) -> str:
        return f"{self.assets}/people/{code}.jpg"

    def portraits(self) -> None:
        """About 80 % of the students get a photo. Those with a late payment or a weak attendance
        keep their initials: no real person's face carries the demo's alerts."""
        grace = self.students[0].id
        ranked = sorted(self.students, key=lambda row: (row.id != grace, row.id in self.late_students, -self.assiduity[row.id], row.id))
        pools = {gender: list(codes) for gender, codes in STUDENT_PORTRAITS.items()}
        for row in ranked[:round(len(self.students) * PORTRAIT_SHARE)]:
            pool = pools["f" if row.full_name in FEMALE_STUDENTS else "m"]
            if pool:
                row.avatar_url = self.portrait(pool.pop(0))
        self.db.commit()

    def quiet(self) -> None:
        """Nothing leaves the demo school: no email nor WhatsApp to its fictional people."""
        self.db.execute(delete(CommunicationOutboxRecord).where(CommunicationOutboxRecord.organization_id == self.org.id))
        self.db.commit()


def build_demo_school(
    db: Session, *, slug: str = DEMO_SLUG, password: str | None = None, now: datetime | None = None,
    site_url: str | None = None,
) -> dict:
    """Create the demo school. Refuses when a school already uses the address (see remove_demo_school)."""
    if db.scalar(select(OrganizationRecord.id).where(OrganizationRecord.slug == slug)) is not None:
        raise ValueError(f"Une école utilise déjà l'adresse « {slug} ».")
    builder = _Builder(db, slug=slug, password=password, now=now or datetime.now(UTC),
                       site_url=site_url or settings.frontend_url)
    builder.school()
    builder.formations()
    builder.portraits()
    builder.ledger()
    builder.courses()
    builder.classes()
    builder.progress()
    builder.evaluations()
    builder.quiet()
    return {
        "organization_id": builder.org.id,
        "slug": slug,
        "students": len(builder.students),
        "formations": len(builder.cohorts),
        "owner": builder.owner.email,
        "teacher": builder.teachers["Kamla Loïc"].email,
        "student": builder.students[0].email,
    }
