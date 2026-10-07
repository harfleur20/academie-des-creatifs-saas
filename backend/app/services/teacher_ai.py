from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import FormationRecord, FormationSessionRecord, SessionTeacherRecord
from app.schemas.integrations import (
    AiAssignmentDraftPayload,
    AiCourseDraftPayload,
    AiQuizDraftPayload,
)
from app.services.organization_integrations import (
    OPENAI_API_BASE_URL,
    openai_credentials,
)
from app.services.tenancy import TenantContext


AI_TIMEOUT_SECONDS = 180.0


def require_teacher_session(
    db: Session,
    tenant: TenantContext,
    session_id: int,
) -> tuple[FormationSessionRecord, FormationRecord]:
    session = db.get(FormationSessionRecord, session_id)
    if session is None or session.organization_id != tenant.organization_id:
        raise HTTPException(status_code=404, detail="Session introuvable.")

    if tenant.user.platform_role != "super_admin" and not tenant.organization_roles.intersection({"owner", "admin", "manager"}):
        assigned = db.scalar(
            select(SessionTeacherRecord.id).where(
                SessionTeacherRecord.organization_id == tenant.organization_id,
                SessionTeacherRecord.session_id == session_id,
                SessionTeacherRecord.teacher_id == tenant.user.id,
            )
        )
        if assigned is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Vous n’êtes pas affecté à cette session.",
            )

    formation = db.get(FormationRecord, session.formation_id)
    if formation is None or formation.organization_id != tenant.organization_id:
        raise HTTPException(status_code=404, detail="Formation introuvable.")
    return session, formation


def _extract_response_text(payload: dict[str, Any]) -> str:
    direct = payload.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()

    parts: list[str] = []
    for item in payload.get("output", []) if isinstance(payload.get("output"), list) else []:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            text = block.get("text")
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
    return "\n".join(parts).strip()


def _parse_json_text(value: str) -> dict[str, Any]:
    cleaned = value.strip()
    fenced = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, re.DOTALL | re.IGNORECASE)
    if fenced:
        cleaned = fenced.group(1).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OpenAI a renvoyé un brouillon dans un format invalide. Réessayez.",
        ) from exc
    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OpenAI n’a pas renvoyé un objet de brouillon valide.",
        )
    return parsed


def _generate_json(
    db: Session,
    tenant: TenantContext,
    *,
    instructions: str,
    prompt: str,
    max_output_tokens: int = 9000,
) -> dict[str, Any]:
    api_key, model, record = openai_credentials(db, tenant)
    try:
        with httpx.Client(timeout=AI_TIMEOUT_SECONDS) as client:
            response = client.post(
                f"{OPENAI_API_BASE_URL}/responses",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "instructions": instructions,
                    "input": prompt,
                    "max_output_tokens": max_output_tokens,
                },
            )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OpenAI est momentanément inaccessible. Réessayez dans quelques instants.",
        ) from exc

    record.last_tested_at = datetime.now(UTC)
    if response.status_code >= 400:
        if response.status_code in {401, 403}:
            record.status = "error"
            record.last_error = "La clé OpenAI doit être vérifiée dans Connect."
            db.commit()
        if response.status_code == 429:
            detail = "Le quota ou la limite OpenAI de l’école est atteint."
        elif response.status_code in {401, 403}:
            detail = "La connexion OpenAI de l’école n’est plus valide. Reconnectez-la dans Connect."
        else:
            detail = f"OpenAI a refusé la génération (statut {response.status_code})."
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail)

    record.status = "connected"
    record.last_error = None
    db.commit()
    text = _extract_response_text(response.json())
    if not text:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="OpenAI n’a renvoyé aucun contenu exploitable.",
        )
    return _parse_json_text(text)


def _context_line(session: FormationSessionRecord, formation: FormationRecord) -> str:
    return f"Formation : {formation.title}. Session : {session.label}."


def generate_course_draft(
    db: Session,
    tenant: TenantContext,
    payload: AiCourseDraftPayload,
) -> dict[str, Any]:
    session, formation = require_teacher_session(db, tenant, payload.session_id)
    instructions = (
        "Tu es un ingénieur pédagogique francophone. Génère uniquement du JSON valide, sans Markdown. "
        "Le cours doit être concret, progressif et directement exploitable par un formateur. "
        "Chaque leçon contient un contenu pédagogique synthétique, pas seulement un titre."
    )
    prompt = f"""{_context_line(session, formation)}
Sujet / brief : {payload.topic}
Niveau : {payload.level or 'à déduire du contexte'}
Objectifs : {payload.objectives or 'à déduire du sujet'}
Nombre de chapitres : {payload.chapters_count}
Leçons par chapitre : {payload.lessons_per_chapter}

Retourne exactement cette structure JSON :
{{
  "title": "Titre du cours",
  "description": "Description courte",
  "chapters": [
    {{"title": "Titre du chapitre", "lessons": [{{"title": "Titre de la leçon", "content": "Contenu pédagogique"}}]}}
  ]
}}
Respecte exactement le nombre demandé de chapitres et de leçons."""
    return _generate_json(db, tenant, instructions=instructions, prompt=prompt, max_output_tokens=12000)


def generate_quiz_draft(
    db: Session,
    tenant: TenantContext,
    payload: AiQuizDraftPayload,
) -> dict[str, Any]:
    session, formation = require_teacher_session(db, tenant, payload.session_id)
    instructions = (
        "Tu es un concepteur d’évaluations pédagogiques francophone. Génère uniquement du JSON valide, sans Markdown. "
        "Les questions doivent être non ambiguës, avoir exactement une bonne réponse et des distracteurs plausibles."
    )
    prompt = f"""{_context_line(session, formation)}
Sujet / brief : {payload.topic}
Niveau : {payload.level or 'à déduire du contexte'}
Objectifs : {payload.objectives or 'à déduire du sujet'}
Questions : {payload.questions_count}
Choix par question : {payload.options_per_question}

Retourne exactement :
{{
  "title": "Titre du quiz",
  "duration_minutes": 30,
  "questions": [
    {{"text": "Question", "options": ["A", "B", "C", "D"], "correct_index": 0}}
  ]
}}
Chaque question doit contenir exactement {payload.options_per_question} options."""
    return _generate_json(db, tenant, instructions=instructions, prompt=prompt, max_output_tokens=10000)


def generate_assignment_draft(
    db: Session,
    tenant: TenantContext,
    payload: AiAssignmentDraftPayload,
) -> dict[str, Any]:
    session, formation = require_teacher_session(db, tenant, payload.session_id)
    instructions = (
        "Tu es un formateur et ingénieur pédagogique francophone. Génère uniquement du JSON valide, sans Markdown. "
        "Le devoir doit être réaliste, orienté pratique, progressif et directement exploitable. "
        "Le barème evaluation_criteria doit totaliser exactement 20 points."
    )
    prompt = f"""{_context_line(session, formation)}
Sujet / brief : {payload.topic}
Niveau : {payload.level or 'à déduire du contexte'}
Objectifs : {payload.objectives or 'à déduire du sujet'}
Type de travail : {payload.assignment_type or 'travail pratique'}
Projet final : {'oui' if payload.is_final_project else 'non'}
Durée prévue : {payload.duration_days} jours

Retourne exactement :
{{
  "title": "Titre du devoir",
  "brief": {{
    "context": "Contexte professionnel ou pédagogique clair",
    "objective": "Objectif principal mesurable",
    "deliverables": ["Livrable 1", "Livrable 2"],
    "steps": ["Étape 1", "Étape 2", "Étape 3"],
    "evaluation_criteria": [
      {{"label": "Critère", "points": 5, "description": "Ce qui est évalué"}}
    ],
    "submission_method": "Format et modalité de rendu",
    "tips": ["Conseil utile 1", "Conseil utile 2"]
  }},
  "instructions": "Consignes complémentaires complètes et structurées",
  "is_final_project": {str(payload.is_final_project).lower()},
  "duration_days": {payload.duration_days}
}}
Le tableau evaluation_criteria doit contenir un barème dont la somme des points vaut exactement 20."""
    return _generate_json(db, tenant, instructions=instructions, prompt=prompt, max_output_tokens=8000)
