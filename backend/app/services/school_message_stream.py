"""Database-backed message change snapshots shared across API workers."""
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from app.models.entities import SchoolMessageParticipantRecord, SchoolMessageRecord
from app.services.tenancy import TenantContext


def message_snapshot(db: Session, tenant: TenantContext) -> tuple[int, int]:
    participant = SchoolMessageParticipantRecord
    message = SchoolMessageRecord
    newest, unread = db.execute(select(
        func.coalesce(func.max(message.id), 0),
        func.coalesce(func.sum(case((
            and_(
                message.sender_user_id != tenant.user.id,
                or_(
                    participant.last_read_at.is_(None),
                    message.created_at > participant.last_read_at,
                ),
            ),
            1,
        ), else_=0)), 0),
    ).select_from(participant).outerjoin(message, (
        (message.thread_id == participant.thread_id)
        & (message.organization_id == tenant.organization_id)
    )).where(
        participant.organization_id == tenant.organization_id,
        participant.user_id == tenant.user.id,
    )).one()
    return int(newest), int(unread)
