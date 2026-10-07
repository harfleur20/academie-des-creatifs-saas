from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.dependencies import get_tenant_context
from app.db.session import get_db
from app.schemas.integrations import (
    AiAssignmentDraft,
    AiAssignmentDraftPayload,
    AiCourseDraft,
    AiCourseDraftPayload,
    AiQuizDraft,
    AiQuizDraftPayload,
    OpenAIIntegrationRead,
)
from app.services.organization_integrations import OPENAI_PROVIDER, get_integration
from app.services.teacher_ai import (
    generate_assignment_draft,
    generate_course_draft,
    generate_quiz_draft,
)
from app.services.tenancy import TenantContext, require_organization_roles


router = APIRouter(prefix="/teacher/ai", tags=["teacher-ai"])


def _require_teacher_access(tenant: TenantContext) -> None:
    require_organization_roles(tenant, "owner", "admin", "manager", "teacher")


def _validate_draft(model_type, data):
    try:
        return model_type.model_validate(data)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Le brouillon généré par OpenAI n’a pas la structure attendue. Réessayez.",
        ) from exc


@router.get("/status", response_model=OpenAIIntegrationRead)
def teacher_ai_status_route(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    _require_teacher_access(tenant)
    record = get_integration(db, tenant, OPENAI_PROVIDER)
    if record is None:
        return OpenAIIntegrationRead(connected=False, status="disconnected")
    return OpenAIIntegrationRead(
        connected=record.status == "connected",
        status=record.status,
        model=record.model,
        connected_at=record.connected_at,
        last_tested_at=record.last_tested_at,
        last_error=record.last_error,
    )


@router.post("/course-draft", response_model=AiCourseDraft)
def teacher_ai_course_draft_route(
    payload: AiCourseDraftPayload,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    _require_teacher_access(tenant)
    return _validate_draft(AiCourseDraft, generate_course_draft(db, tenant, payload))


@router.post("/quiz-draft", response_model=AiQuizDraft)
def teacher_ai_quiz_draft_route(
    payload: AiQuizDraftPayload,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    _require_teacher_access(tenant)
    return _validate_draft(AiQuizDraft, generate_quiz_draft(db, tenant, payload))


@router.post("/assignment-draft", response_model=AiAssignmentDraft)
def teacher_ai_assignment_draft_route(
    payload: AiAssignmentDraftPayload,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    _require_teacher_access(tenant)
    return _validate_draft(AiAssignmentDraft, generate_assignment_draft(db, tenant, payload))
