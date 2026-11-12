from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from test_assignment_publication import days_from_now, draft, school, sent_events, tenant_for

from app.api.dependencies import get_tenant_context
from app.db.session import get_db
from app.main import app
from app.models.entities import SessionCourseDayRecord
from app.schemas.assignments import AssignmentBrief, AssignmentUpdate
from app.services.assignments import list_student_assignments, list_teacher_assignments, publish_assignment, update_assignment
from app.services.learning_progress import badge_for_enrollment, progress_for_enrollment


UPDATED = "student.assignment.updated"


def brief(**values):
    return {
        "context": "Une marque locale change de logo.",
        "objective": "Concevoir une affiche.",
        "deliverables": ["Affiche PDF", "Note d'intention"],
        "steps": ["Analyser", "Maquetter", "Finaliser"],
        "evaluation_criteria": [
            {"label": "Composition", "points": 12, "description": "Hiérarchie claire."},
            {"label": "Typographie", "points": 8, "description": "Lisibilité."},
        ],
        "submission_method": "Un PDF de moins de 10 Mo.",
        "tips": ["Partez d'une grille."],
        **values,
    }


@pytest.mark.parametrize(
    "values",
    [
        {"objective": "   "},
        {"objective": "<b></b>"},
        {"deliverables": []},
        {"deliverables": ["   "]},
        {"steps": []},
        {"submission_method": " "},
        {"evaluation_criteria": []},
        {"evaluation_criteria": [{"label": "Seul", "points": 19, "description": "Pas 20."}]},
        {"evaluation_criteria": [{"label": "Trop", "points": 21, "description": "Plus de 20."}]},
        {"evaluation_criteria": [{"label": " ", "points": 20, "description": "Sans nom."}]},
        {"deliverables": [f"Livrable {index}" for index in range(9)]},
        {"tips": [f"Conseil {index}" for index in range(7)]},
    ],
)
def test_incomplete_sheet_is_refused(values):
    with pytest.raises(ValidationError):
        AssignmentBrief(**brief(**values))


def test_sheet_text_is_cleaned():
    cleaned = AssignmentBrief(**brief(
        objective="<script>alert(1)</script>Concevoir<br>une  affiche",
        deliverables=["Affiche", "affiche ", "  ", "Note"],
    ))
    assert cleaned.objective == "alert(1)Concevoir\nune affiche"
    assert cleaned.deliverables == ["Affiche", "Note"]


def test_scale_may_use_half_points():
    criteria = [
        {"label": "A", "points": 12.5, "description": "a"},
        {"label": "B", "points": 7.5, "description": "b"},
    ]
    assert len(AssignmentBrief(**brief(evaluation_criteria=criteria)).evaluation_criteria) == 2


def test_teacher_writes_a_sheet_and_the_student_reads_it():
    db, org, teacher, student, session, _enrollment = school()
    created = draft(db, org, teacher, session, brief=brief())
    tenant = tenant_for(db, org, teacher)
    assert created.brief.objective == "Concevoir une affiche."
    assert list_teacher_assignments(db, tenant, session.id)[0].brief.tips == ["Partez d'une grille."]
    publish_assignment(db, tenant, created.id)
    [item] = list_student_assignments(db, tenant_for(db, org, student))
    assert [criterion.points for criterion in item.brief.evaluation_criteria] == [12, 8]


def test_assignment_without_sheet_keeps_its_free_instructions():
    db, org, teacher, student, session, _enrollment = school()
    created = draft(db, org, teacher, session, instructions="Consigne libre")
    assert created.brief is None
    publish_assignment(db, tenant_for(db, org, teacher), created.id)
    [item] = list_student_assignments(db, tenant_for(db, org, student))
    assert (item.brief, item.instructions) == (None, "Consigne libre")


def test_locked_assignment_hides_its_sheet():
    db, org, teacher, student, session, _enrollment = school()
    day = SessionCourseDayRecord(
        organization_id=org.id, session_id=session.id, teacher_id=teacher.id, title="À venir",
        scheduled_at=days_from_now(2), duration_minutes=90,
    )
    db.add(day)
    db.commit()
    created = draft(db, org, teacher, session, course_day_id=day.id, brief=brief())
    publish_assignment(db, tenant_for(db, org, teacher), created.id)
    [item] = list_student_assignments(db, tenant_for(db, org, student))
    assert item.is_locked is True
    assert item.brief is None


def test_teacher_adds_changes_and_removes_a_sheet():
    db, org, teacher, _student, session, _enrollment = school()
    created = draft(db, org, teacher, session)
    tenant = tenant_for(db, org, teacher)
    added = update_assignment(db, tenant, created.id, AssignmentUpdate(brief=brief()))
    assert added.brief.objective == "Concevoir une affiche."
    changed = update_assignment(db, tenant, created.id, AssignmentUpdate(brief=brief(objective="Refaire le logo.")))
    assert changed.brief.objective == "Refaire le logo."
    kept = update_assignment(db, tenant, created.id, AssignmentUpdate(title="Autre titre"))
    assert kept.brief.objective == "Refaire le logo."
    assert update_assignment(db, tenant, created.id, AssignmentUpdate(brief=None)).brief is None


def test_students_are_told_when_the_sheet_of_a_published_assignment_changes():
    db, org, teacher, _student, session, _enrollment = school()
    created = draft(db, org, teacher, session, brief=brief())
    tenant = tenant_for(db, org, teacher)
    publish_assignment(db, tenant, created.id)
    update_assignment(db, tenant, created.id, AssignmentUpdate(brief=brief()))
    assert sent_events(db, UPDATED) == []
    update_assignment(db, tenant, created.id, AssignmentUpdate(brief=brief(objective="Nouvel objectif.")))
    assert len(sent_events(db, UPDATED)) == 1


def test_a_tp_counts_exactly_like_an_assignment_once_published():
    db, org, teacher, student, session, enrollment = school()
    free = draft(db, org, teacher, session, title="Devoir libre", days=3)
    sheet = draft(db, org, teacher, session, title="TP structuré", days=3, brief=brief())
    tenant = tenant_for(db, org, student)
    assert progress_for_enrollment(db, tenant, enrollment).total_assignments == 0

    teacher_tenant = tenant_for(db, org, teacher)
    publish_assignment(db, teacher_tenant, free.id)
    assert progress_for_enrollment(db, tenant, enrollment).total_assignments == 1
    publish_assignment(db, teacher_tenant, sheet.id)
    assert progress_for_enrollment(db, tenant, enrollment).total_assignments == 2
    # Both are open and not due yet: the badge lists them alike as work that can raise it.
    upcoming = badge_for_enrollment(db, tenant, enrollment).upcoming
    assert sorted((item.kind, item.title) for item in upcoming) == [("assignment", "Devoir libre"), ("assignment", "TP structuré")]


def test_brief_api_round_trip():
    db, org, teacher, _student, session, _enrollment = school()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_tenant_context] = lambda: tenant_for(db, org, teacher)
    try:
        client = TestClient(app)
        url = f"/api/v1/assignments/teacher/sessions/{session.id}"
        due = (days_from_now(0) + timedelta(days=5)).isoformat()
        created = client.post(url, json={"title": "TP", "due_date": due, "brief": brief()})
        wrong_scale = client.post(url, json={
            "title": "TP", "due_date": due,
            "brief": brief(evaluation_criteria=[{"label": "A", "points": 5, "description": "a"}]),
        })
        cleared = client.patch(f"/api/v1/assignments/teacher/{created.json()['id']}", json={"brief": None})
    finally:
        app.dependency_overrides.clear()
    assert created.status_code == 201
    assert created.json()["brief"]["objective"] == "Concevoir une affiche."
    assert wrong_scale.status_code == 422
    assert cleared.json()["brief"] is None
