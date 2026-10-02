from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import (
    CommunicationOutboxRecord,
    EnrollmentRecord,
    OrganizationRecord,
    UserRecord,
)
from app.services.school_branding import branding_snapshot


@dataclass(frozen=True)
class SchoolMessageTemplate:
    subject: str
    body: str


class _SafeContext(dict[str, object]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


SCHOOL_MESSAGE_TEMPLATES: dict[str, SchoolMessageTemplate] = {
    "student.welcome": SchoolMessageTemplate(
        "Bienvenue dans votre espace étudiant",
        "Bonjour {recipient_name},\nbienvenue à {school_name}. Votre espace étudiant est maintenant ouvert.\nVotre matricule est {student_code}.",
    ),
    "student.payment.confirmed": SchoolMessageTemplate(
        "Paiement confirmé",
        "Bonjour {recipient_name},\nvotre paiement pour {formation_title} — {session_label} est confirmé.\nVotre matricule est {student_code}.",
    ),
    "student.payment.due": SchoolMessageTemplate(
        "Échéance de paiement à régler",
        "Bonjour {recipient_name},\nune échéance de {amount_label} pour {formation_title} est arrivée à échéance.\nVous disposez du délai de grâce jusqu'au {grace_date}.",
    ),
    "student.payment.overdue": SchoolMessageTemplate(
        "Échéance impayée",
        "Bonjour {recipient_name},\nune échéance de {amount_label} pour {formation_title} est en retard.",
    ),
    "student.access.suspended": SchoolMessageTemplate(
        "Accès pédagogique suspendu",
        "Bonjour {recipient_name},\nvotre accès pédagogique est suspendu à la suite d'un impayé. Vos travaux, notes et votre progression restent conservés.",
    ),
    "student.access.reactivated": SchoolMessageTemplate(
        "Accès pédagogique réactivé",
        "Bonjour {recipient_name},\nvotre règlement a été pris en compte et votre accès pédagogique est réactivé.",
    ),
    "student.course.published": SchoolMessageTemplate(
        "Nouveau cours disponible",
        "Bonjour {recipient_name},\nle cours « {course_title} » est maintenant disponible dans la session {session_label}.",
    ),
    "student.live.scheduled": SchoolMessageTemplate(
        "Nouvelle séance live programmée",
        "Bonjour {recipient_name},\nla séance « {course_day_title} » est programmée le {scheduled_at} pour la session {session_label}.",
    ),
    "student.assignment.created": SchoolMessageTemplate(
        "Nouveau devoir",
        "Bonjour {recipient_name},\nun nouveau devoir « {assignment_title} » est disponible pour la session {session_label}.\nDate limite : {due_at}.",
    ),
    "student.assignment.reviewed": SchoolMessageTemplate(
        "Votre devoir a été corrigé",
        "Bonjour {recipient_name},\nvotre devoir « {assignment_title} » a été corrigé.\nNote : {score_label}.",
    ),
    "student.quiz.published": SchoolMessageTemplate(
        "Nouveau quiz / examen",
        "Bonjour {recipient_name},\nl'évaluation « {quiz_title} » est maintenant disponible pour la session {session_label}.",
    ),
    "student.quiz.result": SchoolMessageTemplate(
        "Résultat de votre évaluation",
        "Bonjour {recipient_name},\nvotre résultat pour « {quiz_title} » est disponible : {score_pct}%.",
    ),
    "student.certificate.issued": SchoolMessageTemplate(
        "Votre certificat est disponible",
        "Bonjour {recipient_name},\nvotre certificat pour la formation {formation_title} est disponible.\nNuméro : {certificate_number}.",
    ),
    "school.team.invitation": SchoolMessageTemplate(
        "Invitation à rejoindre l'école",
        "Bonjour,\n{inviter_name} vous invite à rejoindre {school_name} en tant que {role_label}.\nAccepter l'invitation : {acceptance_url}\nCette invitation expire dans {expires_days} jours.",
    ),
}


def render_school_event(
    event_key: str,
    *,
    context: Mapping[str, object] | None = None,
) -> SchoolMessageTemplate:
    template = SCHOOL_MESSAGE_TEMPLATES.get(event_key)
    if template is None:
        raise ValueError(f"Template de communication inconnu : {event_key}")
    values = _SafeContext(context or {})
    return SchoolMessageTemplate(
        subject=template.subject.format_map(values),
        body=template.body.format_map(values),
    )


def queue_school_event(
    db: Session,
    *,
    org: OrganizationRecord,
    event_key: str,
    user: UserRecord | None = None,
    recipient_email: str | None = None,
    recipient_phone: str | None = None,
    context: Mapping[str, object] | None = None,
    include_whatsapp: bool = True,
) -> list[CommunicationOutboxRecord]:
    snapshot = branding_snapshot(db, org)
    values = dict(context or {})
    values.setdefault("school_name", snapshot.get("school_name") or org.name)
    if user is not None:
        values.setdefault("recipient_name", user.full_name)
        recipient_email = recipient_email or user.email
        recipient_phone = recipient_phone or user.phone
    else:
        values.setdefault("recipient_name", "")

    rendered = render_school_event(event_key, context=values)
    rows: list[CommunicationOutboxRecord] = []

    if recipient_email:
        row = CommunicationOutboxRecord(
            organization_id=org.id,
            user_id=user.id if user else None,
            channel="email",
            recipient=recipient_email,
            event_key=event_key,
            subject=f"[{snapshot['school_name']}] {rendered.subject}",
            body=f"{rendered.body}\n\n{snapshot.get('email_signature') or snapshot['school_name']}",
            branding_snapshot=snapshot,
            status="pending",
        )
        db.add(row)
        rows.append(row)

    if include_whatsapp and recipient_phone:
        row = CommunicationOutboxRecord(
            organization_id=org.id,
            user_id=user.id if user else None,
            channel="whatsapp",
            recipient=recipient_phone,
            event_key=event_key,
            subject=None,
            body=f"{rendered.body}\n\n{snapshot.get('whatsapp_signature') or snapshot['school_name']}",
            branding_snapshot=snapshot,
            status="pending",
        )
        db.add(row)
        rows.append(row)

    return rows


def queue_session_students_event(
    db: Session,
    *,
    org: OrganizationRecord,
    session_id: int,
    event_key: str,
    context: Mapping[str, object] | None = None,
) -> int:
    users = list(
        db.scalars(
            select(UserRecord)
            .join(EnrollmentRecord, EnrollmentRecord.student_id == UserRecord.id)
            .where(
                EnrollmentRecord.organization_id == org.id,
                EnrollmentRecord.session_id == session_id,
                EnrollmentRecord.status.in_(["active", "completed"]),
                UserRecord.status == "active",
            )
            .distinct()
        ).all()
    )
    for user in users:
        queue_school_event(
            db,
            org=org,
            event_key=event_key,
            user=user,
            context=context,
        )
    return len(users)
