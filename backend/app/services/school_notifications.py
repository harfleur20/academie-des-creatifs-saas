"""Durable, tenant-scoped in-app notifications."""
from datetime import UTC, datetime
from typing import Literal

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from app.models.entities import EnrollmentRecord, OrganizationMemberRecord, SchoolNotificationRecord, UserRecord
from app.services.membership_roles import effective_member_roles
from app.services.tenancy import TenantContext


MANAGER_ROLES = {"owner", "admin", "manager"}
NotificationAudience = Literal["manage", "teacher", "student"]


def allowed_audiences(tenant: TenantContext) -> set[str]:
    if tenant.support_mode or tenant.user.platform_role == "super_admin":
        return {"manage"}
    audiences: set[str] = set()
    if tenant.organization_roles.intersection(MANAGER_ROLES):
        audiences.add("manage")
    if "teacher" in tenant.organization_roles:
        audiences.add("teacher")
    if "student" in tenant.organization_roles:
        audiences.add("student")
    return audiences


def notify_user(
    db: Session, *, organization_id: int, user_id: int, event_key: str,
    title: str, message: str, audience: NotificationAudience,
    category: str = "system", tone: str = "info",
    action_label: str | None = None, action_path: str | None = None,
) -> SchoolNotificationRecord:
    """Queue the event in the caller's business transaction."""
    audience_path = f"/app/{audience}"
    if action_path is not None and (
        not (action_path == audience_path or action_path.startswith(audience_path + "/"))
        or "//" in action_path or "\\" in action_path
    ):
        raise ValueError("Notification action must use a local workspace path")
    existing = db.scalar(select(SchoolNotificationRecord).where(
        SchoolNotificationRecord.organization_id == organization_id,
        SchoolNotificationRecord.user_id == user_id,
        SchoolNotificationRecord.event_key == event_key,
    ))
    if existing is not None:
        return existing
    row = SchoolNotificationRecord(
        organization_id=organization_id, user_id=user_id, event_key=event_key,
        audience=audience, title=title, message=message, category=category, tone=tone,
        action_label=action_label, action_path=action_path,
    )
    db.add(row)
    db.flush()
    return row


def notify_school_managers(db: Session, *, organization_id: int, event_key: str,
                           title: str, message: str, category: str = "admin",
                           tone: str = "info", action_label: str | None = None,
                           action_path: str | None = None) -> None:
    members = db.scalars(select(OrganizationMemberRecord).options(
        selectinload(OrganizationMemberRecord.roles),
        selectinload(OrganizationMemberRecord.user),
    ).where(
        OrganizationMemberRecord.organization_id == organization_id,
        OrganizationMemberRecord.status == "active",
    )).all()
    for member in members:
        if member.user.status != "active" or not effective_member_roles(member).intersection(MANAGER_ROLES):
            continue
        notify_user(
            db, organization_id=organization_id, user_id=member.user_id,
            event_key=event_key, title=title, message=message, audience="manage", category=category,
            tone=tone, action_label=action_label, action_path=action_path,
        )


def notify_session_students(
    db: Session, *, organization_id: int, session_id: int, event_key: str,
    title: str, message: str, category: str = "learning", tone: str = "info",
    action_label: str | None = None, action_path: str | None = None,
    exclude_user_id: int | None = None,
) -> None:
    student_ids = db.scalars(select(EnrollmentRecord.student_id).join(
        UserRecord, UserRecord.id == EnrollmentRecord.student_id,
    ).where(
        EnrollmentRecord.organization_id == organization_id,
        EnrollmentRecord.session_id == session_id,
        EnrollmentRecord.status.in_(["active", "completed"]),
        UserRecord.status == "active",
    ).distinct()).all()
    for student_id in student_ids:
        if student_id == exclude_user_id:
            continue
        notify_user(
            db, organization_id=organization_id, user_id=student_id,
            event_key=event_key, title=title, message=message, audience="student",
            category=category, tone=tone, action_label=action_label, action_path=action_path,
        )


def dismiss_event(db: Session, *, organization_id: int, event_key: str) -> None:
    db.execute(update(SchoolNotificationRecord).where(
        SchoolNotificationRecord.organization_id == organization_id,
        SchoolNotificationRecord.event_key == event_key,
        SchoolNotificationRecord.dismissed_at.is_(None),
    ).values(dismissed_at=datetime.now(UTC)))


def list_notifications(db: Session, tenant: TenantContext, audience: NotificationAudience) -> list[SchoolNotificationRecord]:
    if audience not in allowed_audiences(tenant):
        raise HTTPException(403, "Accès à cet espace refusé.")
    return list(db.scalars(select(SchoolNotificationRecord).where(
        SchoolNotificationRecord.organization_id == tenant.organization_id,
        SchoolNotificationRecord.user_id == tenant.user.id,
        SchoolNotificationRecord.audience == audience,
        SchoolNotificationRecord.dismissed_at.is_(None),
    ).order_by(SchoolNotificationRecord.created_at.desc(), SchoolNotificationRecord.id.desc()).limit(100)).all())


def update_notification_state(db: Session, tenant: TenantContext, ids: list[int], *, dismiss: bool) -> None:
    rows = db.scalars(select(SchoolNotificationRecord).where(
        SchoolNotificationRecord.organization_id == tenant.organization_id,
        SchoolNotificationRecord.user_id == tenant.user.id,
        SchoolNotificationRecord.audience.in_(allowed_audiences(tenant)),
        SchoolNotificationRecord.id.in_(ids),
        SchoolNotificationRecord.dismissed_at.is_(None),
    )).all()
    now = datetime.now(UTC)
    for row in rows:
        if row.read_at is None:
            row.read_at = now
        if dismiss:
            row.dismissed_at = now
    db.commit()
