from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_tenant_context
from app.db.session import get_db
from app.schemas.messages import (
    CreateSchoolMessage, CreateSchoolThread, MessageRecipientRead,
    SchoolMessageRead, SchoolThreadDetail, SchoolThreadRead,
)
from app.services.school_messages import create_thread, get_thread, list_recipients, list_threads, send_message
from app.services.tenancy import TenantContext


router = APIRouter(prefix="/messages", tags=["messages"])


@router.get("/recipients", response_model=list[MessageRecipientRead])
def recipients(db: Session = Depends(get_db), tenant: TenantContext = Depends(get_tenant_context)):
    return list_recipients(db, tenant)


@router.get("/threads", response_model=list[SchoolThreadRead])
def threads(db: Session = Depends(get_db), tenant: TenantContext = Depends(get_tenant_context)):
    return list_threads(db, tenant)


@router.post("/threads", response_model=SchoolThreadDetail, status_code=status.HTTP_201_CREATED)
def new_thread(payload: CreateSchoolThread, db: Session = Depends(get_db), tenant: TenantContext = Depends(get_tenant_context)):
    return create_thread(db, tenant, payload.participant_ids, payload.subject, payload.body)


@router.get("/threads/{thread_id}", response_model=SchoolThreadDetail)
def thread(thread_id: int, db: Session = Depends(get_db), tenant: TenantContext = Depends(get_tenant_context)):
    return get_thread(db, tenant, thread_id)


@router.post("/threads/{thread_id}/messages", response_model=SchoolMessageRead, status_code=status.HTTP_201_CREATED)
def new_message(thread_id: int, payload: CreateSchoolMessage,
                db: Session = Depends(get_db), tenant: TenantContext = Depends(get_tenant_context)):
    return send_message(db, tenant, thread_id, payload.body)
