from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.entities import (
    EnrollmentRecord, OrganizationMemberRecord, SchoolMessageParticipantRecord,
    SchoolMessageRecord, SchoolMessageThreadRecord, SessionTeacherRecord, UserRecord,
)
from app.schemas.messages import MessageRecipientRead, SchoolMessageRead, SchoolThreadDetail, SchoolThreadRead
from app.services.membership_roles import effective_member_roles
from app.services.school_notifications import notify_user
from app.services.tenancy import TenantContext


MANAGER_ROLES = {"owner", "admin", "manager"}


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _active_members(db: Session, org_id: int) -> dict[int, OrganizationMemberRecord]:
    rows = db.scalars(select(OrganizationMemberRecord).options(
        selectinload(OrganizationMemberRecord.roles), selectinload(OrganizationMemberRecord.user),
    ).where(OrganizationMemberRecord.organization_id == org_id, OrganizationMemberRecord.status == "active")).all()
    return {row.user_id: row for row in rows if row.user.status == "active"}


def _role(member: OrganizationMemberRecord) -> str:
    roles = effective_member_roles(member)
    if roles.intersection(MANAGER_ROLES):
        return "admin"
    if "teacher" in roles:
        return "teacher"
    return "student"


def _can_message(db: Session, org_id: int, sender: OrganizationMemberRecord, recipient: OrganizationMemberRecord) -> bool:
    if sender.user_id == recipient.user_id:
        return False
    sender_roles = effective_member_roles(sender)
    recipient_roles = effective_member_roles(recipient)
    if sender_roles.intersection(MANAGER_ROLES) or recipient_roles.intersection(MANAGER_ROLES):
        return True
    if "teacher" in sender_roles and "student" in recipient_roles:
        return db.scalar(select(EnrollmentRecord.id).join(
            SessionTeacherRecord, SessionTeacherRecord.session_id == EnrollmentRecord.session_id,
        ).where(
            EnrollmentRecord.organization_id == org_id, SessionTeacherRecord.organization_id == org_id,
            EnrollmentRecord.student_id == recipient.user_id, EnrollmentRecord.status == "active",
            SessionTeacherRecord.teacher_id == sender.user_id,
        ).limit(1)) is not None
    if "student" in sender_roles and "teacher" in recipient_roles:
        return _can_message(db, org_id, recipient, sender)
    if "student" in sender_roles and "student" in recipient_roles:
        sender_sessions = select(EnrollmentRecord.session_id).where(
            EnrollmentRecord.organization_id == org_id, EnrollmentRecord.student_id == sender.user_id,
            EnrollmentRecord.status == "active",
        )
        return db.scalar(select(EnrollmentRecord.id).where(
            EnrollmentRecord.organization_id == org_id, EnrollmentRecord.student_id == recipient.user_id,
            EnrollmentRecord.status == "active", EnrollmentRecord.session_id.in_(sender_sessions),
        ).limit(1)) is not None
    return False


def list_recipients(db: Session, tenant: TenantContext) -> list[MessageRecipientRead]:
    members = _active_members(db, tenant.organization_id)
    sender = members.get(tenant.user.id)
    if sender is None:
        raise HTTPException(403, "Adhésion active requise.")
    result = [MessageRecipientRead(id=member.user_id, full_name=member.user.full_name,
                                   role=_role(member), avatar_url=member.user.avatar_url)
              for member in members.values() if _can_message(db, tenant.organization_id, sender, member)]
    return sorted(result, key=lambda item: (item.role, item.full_name.casefold()))


def _require_thread(db: Session, tenant: TenantContext, thread_id: int) -> SchoolMessageThreadRecord:
    thread = db.scalar(select(SchoolMessageThreadRecord).join(
        SchoolMessageParticipantRecord, SchoolMessageParticipantRecord.thread_id == SchoolMessageThreadRecord.id,
    ).where(
        SchoolMessageThreadRecord.id == thread_id,
        SchoolMessageThreadRecord.organization_id == tenant.organization_id,
        SchoolMessageParticipantRecord.organization_id == tenant.organization_id,
        SchoolMessageParticipantRecord.user_id == tenant.user.id,
    ))
    if thread is None:
        raise HTTPException(404, "Conversation introuvable.")
    return thread


def _thread_parts(db: Session, tenant: TenantContext, thread: SchoolMessageThreadRecord):
    parts = db.scalars(select(SchoolMessageParticipantRecord).where(
        SchoolMessageParticipantRecord.organization_id == tenant.organization_id,
        SchoolMessageParticipantRecord.thread_id == thread.id,
    )).all()
    users = {user.id: user for user in db.scalars(select(UserRecord).where(UserRecord.id.in_([part.user_id for part in parts]))).all()}
    messages = db.scalars(select(SchoolMessageRecord).where(
        SchoolMessageRecord.organization_id == tenant.organization_id,
        SchoolMessageRecord.thread_id == thread.id,
    ).order_by(SchoolMessageRecord.created_at, SchoolMessageRecord.id)).all()
    return parts, users, messages


def _serialize_message(message: SchoolMessageRecord, users: dict[int, UserRecord]) -> SchoolMessageRead:
    sender = users.get(message.sender_user_id)
    return SchoolMessageRead(id=message.id, thread_id=message.thread_id, sender_user_id=message.sender_user_id,
                             sender_name=sender.full_name if sender else "Utilisateur", body=message.body,
                             created_at=message.created_at)


def _serialize_thread(db: Session, tenant: TenantContext, thread: SchoolMessageThreadRecord, *, detail: bool = False):
    parts, users, messages = _thread_parts(db, tenant, thread)
    mine = next(part for part in parts if part.user_id == tenant.user.id)
    unread = sum(1 for message in messages if message.sender_user_id != tenant.user.id and
                 (mine.last_read_at is None or _utc(message.created_at) > _utc(mine.last_read_at)))
    data = dict(
        id=thread.id, subject=thread.subject,
        participants=[MessageRecipientRead(id=part.user_id, full_name=users[part.user_id].full_name,
                                           role=part.role_snapshot, avatar_url=users[part.user_id].avatar_url)
                      for part in parts if part.user_id in users],
        last_message=_serialize_message(messages[-1], users) if messages else None,
        unread_count=unread, last_message_at=thread.last_message_at,
    )
    if detail:
        return SchoolThreadDetail(**data, messages=[_serialize_message(message, users) for message in messages])
    return SchoolThreadRead(**data)


def list_threads(db: Session, tenant: TenantContext) -> list[SchoolThreadRead]:
    ids = select(SchoolMessageParticipantRecord.thread_id).where(
        SchoolMessageParticipantRecord.organization_id == tenant.organization_id,
        SchoolMessageParticipantRecord.user_id == tenant.user.id,
    )
    threads = db.scalars(select(SchoolMessageThreadRecord).where(
        SchoolMessageThreadRecord.organization_id == tenant.organization_id,
        SchoolMessageThreadRecord.id.in_(ids),
    ).order_by(SchoolMessageThreadRecord.last_message_at.desc()).limit(100)).all()
    return [_serialize_thread(db, tenant, thread) for thread in threads]


def get_thread(db: Session, tenant: TenantContext, thread_id: int) -> SchoolThreadDetail:
    thread = _require_thread(db, tenant, thread_id)
    participant = db.scalar(select(SchoolMessageParticipantRecord).where(
        SchoolMessageParticipantRecord.organization_id == tenant.organization_id,
        SchoolMessageParticipantRecord.thread_id == thread_id,
        SchoolMessageParticipantRecord.user_id == tenant.user.id,
    ))
    assert participant is not None
    participant.last_read_at = datetime.now(UTC)
    db.commit()
    return _serialize_thread(db, tenant, thread, detail=True)


def _notify_participants(db: Session, tenant: TenantContext, thread: SchoolMessageThreadRecord, message: SchoolMessageRecord) -> None:
    members = _active_members(db, tenant.organization_id)
    ids = db.scalars(select(SchoolMessageParticipantRecord.user_id).where(
        SchoolMessageParticipantRecord.organization_id == tenant.organization_id,
        SchoolMessageParticipantRecord.thread_id == thread.id,
        SchoolMessageParticipantRecord.user_id != tenant.user.id,
    )).all()
    for user_id in ids:
        member = members.get(user_id)
        if member is None:
            continue
        role = _role(member)
        audience = "manage" if role == "admin" else role
        notify_user(db, organization_id=tenant.organization_id, user_id=user_id,
                    event_key=f"school-message:{message.id}:{user_id}", title="Nouveau message",
                    message=f"{tenant.user.full_name} : {message.body[:120]}", audience=audience,
                    category="message", action_label="Lire", action_path=f"/app/{audience}/messages")


def create_thread(db: Session, tenant: TenantContext, recipient_ids: list[int], subject: str, body: str) -> SchoolThreadDetail:
    if not body.strip() or len(set(recipient_ids)) != len(recipient_ids) or len(recipient_ids) > 8 or not recipient_ids:
        raise HTTPException(422, "Destinataires ou message invalides.")
    members = _active_members(db, tenant.organization_id)
    sender = members.get(tenant.user.id)
    if sender is None:
        raise HTTPException(403, "Adhésion active requise.")
    for recipient_id in recipient_ids:
        recipient = members.get(recipient_id)
        if recipient is None or not _can_message(db, tenant.organization_id, sender, recipient):
            raise HTTPException(403, "Destinataire non autorisé.")
    now = datetime.now(UTC)
    thread = SchoolMessageThreadRecord(organization_id=tenant.organization_id,
                                      subject=subject.strip() or "Nouvelle conversation",
                                      created_by_user_id=tenant.user.id, last_message_at=now)
    db.add(thread)
    db.flush()
    for user_id in [tenant.user.id, *recipient_ids]:
        member = members[user_id]
        db.add(SchoolMessageParticipantRecord(organization_id=tenant.organization_id, thread_id=thread.id,
                                              user_id=user_id, role_snapshot=_role(member),
                                              last_read_at=now if user_id == tenant.user.id else None))
    message = SchoolMessageRecord(organization_id=tenant.organization_id, thread_id=thread.id,
                                  sender_user_id=tenant.user.id, body=body.strip(), created_at=now)
    db.add(message)
    db.flush()
    _notify_participants(db, tenant, thread, message)
    db.commit()
    return get_thread(db, tenant, thread.id)


def send_message(db: Session, tenant: TenantContext, thread_id: int, body: str) -> SchoolMessageRead:
    if not body.strip():
        raise HTTPException(422, "Renseignez un message.")
    thread = _require_thread(db, tenant, thread_id)
    now = datetime.now(UTC)
    message = SchoolMessageRecord(organization_id=tenant.organization_id, thread_id=thread_id,
                                  sender_user_id=tenant.user.id, body=body.strip(), created_at=now)
    thread.last_message_at = now
    participant = db.scalar(select(SchoolMessageParticipantRecord).where(
        SchoolMessageParticipantRecord.organization_id == tenant.organization_id,
        SchoolMessageParticipantRecord.thread_id == thread_id,
        SchoolMessageParticipantRecord.user_id == tenant.user.id,
    ))
    assert participant is not None
    participant.last_read_at = now
    db.add(message)
    db.flush()
    _notify_participants(db, tenant, thread, message)
    db.commit()
    db.refresh(message)
    return _serialize_message(message, {tenant.user.id: tenant.user})
