from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.dependencies import get_tenant_context
from app.db.session import get_db
from app.models.entities import ClassDiscussionPostRecord, ClassDiscussionReplyRecord
from app.services.academic_access import can_view_session
from app.services.tenancy import TenantContext


router = APIRouter(prefix="/academic", tags=["academic"])


@router.delete(
    "/classes/{session_id}/discussion/{post_id}/replies/{reply_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_class_reply(
    session_id: int,
    post_id: int,
    reply_id: int,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    if tenant.support_mode:
        raise HTTPException(403, "Le mode support est en lecture seule.")
    if not can_view_session(db, tenant, session_id):
        raise HTTPException(403, "Vous n'avez pas accès à cette classe.")

    post = db.scalar(
        select(ClassDiscussionPostRecord).where(
            ClassDiscussionPostRecord.id == post_id,
            ClassDiscussionPostRecord.organization_id == tenant.organization_id,
            ClassDiscussionPostRecord.session_id == session_id,
        )
    )
    if post is None:
        raise HTTPException(404, "Publication introuvable.")

    reply = db.scalar(
        select(ClassDiscussionReplyRecord).where(
            ClassDiscussionReplyRecord.id == reply_id,
            ClassDiscussionReplyRecord.organization_id == tenant.organization_id,
            ClassDiscussionReplyRecord.post_id == post.id,
        )
    )
    if reply is None:
        raise HTTPException(404, "Commentaire introuvable.")
    if reply.author_user_id != tenant.user.id:
        raise HTTPException(403, "Vous ne pouvez supprimer que vos commentaires.")

    db.delete(reply)
    db.commit()
