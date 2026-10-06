import asyncio

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from starlette.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from app.api.dependencies import get_tenant_context
from app.core.security import create_message_ws_ticket, decode_message_ws_ticket
from app.db.session import SessionLocal, get_db
from app.models.entities import UserRecord
from app.schemas.messages import (
    CreateSchoolMessage, CreateSchoolThread, MessageRecipientRead,
    SchoolMessageRead, SchoolThreadDetail, SchoolThreadRead,
)
from app.services.school_messages import create_thread, get_thread, list_recipients, list_threads, send_message
from app.services.school_message_stream import message_snapshot
from app.services.tenancy import TenantContext, resolve_tenant_context


router = APIRouter(prefix="/messages", tags=["messages"])


@router.get("/ws-ticket")
def websocket_ticket(tenant: TenantContext = Depends(get_tenant_context)) -> dict[str, str]:
    if tenant.support_mode or tenant.user.platform_role == "super_admin":
        raise HTTPException(403, "Messagerie temps réel indisponible en mode support.")
    return {"ticket": create_message_ws_ticket(
        tenant.user.id, tenant.organization_id, tenant.user.session_version,
    )}


def _validated_snapshot(ticket: str) -> tuple[int, int] | None:
    payload = decode_message_ws_ticket(ticket)
    if payload is None:
        return None
    try:
        user_id = int(str(payload["sub"]))
        organization_id = int(str(payload["organization_id"]))
        version = payload["session_version"]
    except (KeyError, TypeError, ValueError):
        return None
    if type(version) is not int:
        return None
    with SessionLocal() as db:
        user = db.get(UserRecord, user_id)
        if user is None or user.status != "active" or user.platform_role == "super_admin" or user.session_version != version:
            return None
        try:
            tenant = resolve_tenant_context(db, user=user, organization_id=organization_id)
        except HTTPException:
            return None
        return message_snapshot(db, tenant)


@router.websocket("/ws")
async def messages_websocket(websocket: WebSocket) -> None:
    protocols = websocket.scope.get("subprotocols", [])
    ticket = protocols[1] if len(protocols) == 2 and protocols[0] == "school-messages" else ""
    snapshot = await run_in_threadpool(_validated_snapshot, ticket)
    if snapshot is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return
    await websocket.accept(subprotocol="school-messages")
    previous = snapshot
    await websocket.send_json({"type": "messages.summary", "unread_count": snapshot[1]})
    try:
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=3)
            except TimeoutError:
                pass
            snapshot = await run_in_threadpool(_validated_snapshot, ticket)
            if snapshot is None:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return
            if snapshot != previous:
                await websocket.send_json({"type": "messages.changed", "unread_count": snapshot[1]})
                previous = snapshot
    except WebSocketDisconnect:
        return


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
