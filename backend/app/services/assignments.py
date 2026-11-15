from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from fastapi import HTTPException
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session
from app.models.entities import AssignmentCommentRecord, AssignmentRecord, AssignmentSubmissionRecord, EnrollmentRecord, FormationRecord, FormationSessionRecord, GradeRecord, LessonRecord, OrganizationRecord, SessionCourseDayRecord, SessionTeacherRecord, UserRecord
from app.schemas.assignments import *
from app.services.grades import upsert_grade
from app.services.assets import validate_submission_asset
from app.services.lesson_completion import complete_activity_lessons
from app.services.pedagogy_access import WORK_CLOSED_MESSAGE, current_utc, dashboard_type, guided_activity_available, guided_work_closed, linked_lesson_gate, session_starts_at
from app.services.school_communications import queue_school_event, queue_session_students_event
from app.services.school_notifications import notify_user
from app.services.training_notifications import email_new_submission
from app.services.program_versions import FROZEN_MESSAGE, is_frozen_requirement
from app.services.tenancy import TenantContext

def _utc(v:datetime)->datetime: return v.astimezone(UTC).replace(tzinfo=None) if v.tzinfo else v
def _session(db,tenant,sid):
    s=db.scalar(select(FormationSessionRecord).where(FormationSessionRecord.id==sid,FormationSessionRecord.organization_id==tenant.organization_id))
    if not s: raise HTTPException(404,"Session introuvable.")
    return s
def _teacher_assigned(db,tenant,sid):
    return db.scalar(select(SessionTeacherRecord).where(SessionTeacherRecord.organization_id==tenant.organization_id,SessionTeacherRecord.session_id==sid,SessionTeacherRecord.teacher_id==tenant.user.id))
def _enrollment(db,tenant,sid):
    return db.scalar(select(EnrollmentRecord).where(EnrollmentRecord.organization_id==tenant.organization_id,EnrollmentRecord.session_id==sid,EnrollmentRecord.student_id==tenant.user.id,EnrollmentRecord.status.in_(["active","completed"])))
def _assignment(db,tenant,aid):
    a=db.scalar(select(AssignmentRecord).where(AssignmentRecord.id==aid,AssignmentRecord.organization_id==tenant.organization_id))
    if not a: raise HTTPException(404,"Devoir introuvable.")
    return a
def _published_assignment(db,tenant,aid):
    a=_assignment(db,tenant,aid)
    if a.publication_status!="published": raise HTTPException(404,"Devoir introuvable.")
    return a
def _owned_assignment(db,tenant,aid):
    a=_assignment(db,tenant,aid)
    if tenant.support_mode: raise HTTPException(403,"Le mode support est en lecture seule.")
    if not _teacher_assigned(db,tenant,a.session_id): raise HTTPException(403,"Cette session ne vous est pas affectée.")
    if a.teacher_id!=tenant.user.id: raise HTTPException(403,"Ce devoir appartient à un autre professeur. Vous pouvez le consulter, mais pas le modifier.")
    return a
def _own_course_day(db,tenant,sid,day_id):
    day=db.scalar(select(SessionCourseDayRecord).where(SessionCourseDayRecord.id==day_id,SessionCourseDayRecord.organization_id==tenant.organization_id,SessionCourseDayRecord.session_id==sid))
    if not day: raise HTTPException(422,"Le créneau ne correspond pas à cette session.")
    if day.teacher_id!=tenant.user.id: raise HTTPException(403,"Vous ne pouvez rattacher un devoir qu'à l'un de vos créneaux.")
    return day
def _check_due_date(s,day,due_date):
    if day and _utc(due_date)<_utc(day.scheduled_at): raise HTTPException(422,"La date limite doit être postérieure au créneau.")
    start=datetime.combine(s.start_date,time.min); end=datetime.combine(s.end_date,time.max)
    due=_utc(due_date)
    if due<start or due>end: raise HTTPException(422,"La date limite doit rester dans les dates de la session.")
def _delete_blocked_reason(db,a):
    if is_frozen_requirement(db,a.session_id,"final_project_ids" if a.is_final_project else "assignment_ids",a.id):
        return "Un devoir du programme figé de la session ne peut pas être supprimé."
    if db.scalar(select(LessonRecord.id).where(LessonRecord.organization_id==a.organization_id,LessonRecord.assignment_id==a.id)) is not None:
        return "Un devoir associé à une leçon ne peut pas être supprimé."
    if db.scalar(select(AssignmentSubmissionRecord.id).where(AssignmentSubmissionRecord.organization_id==a.organization_id,AssignmentSubmissionRecord.assignment_id==a.id)) is not None:
        return "Un devoir avec des travaux remis ne peut pas être supprimé."
    return None
def _count_comments(db,a,e): return int(db.scalar(select(func.count(AssignmentCommentRecord.id)).where(AssignmentCommentRecord.assignment_id==a,AssignmentCommentRecord.enrollment_id==e)) or 0)
def _teacher_name(db,a): return db.get(UserRecord,a.teacher_id).full_name if a.teacher_id and db.get(UserRecord,a.teacher_id) else None
def _formation_title(db,sid):
    row=db.execute(select(FormationRecord.title).join(FormationSessionRecord,FormationSessionRecord.formation_id==FormationRecord.id).where(FormationSessionRecord.id==sid)).scalar_one_or_none()
    return row or ""
def _session_label(db,sid): return db.get(FormationSessionRecord,sid).label
def _teacher_view(db,tenant,a):
    return AssignmentRead(id=a.id,session_id=a.session_id,course_day_id=a.course_day_id,teacher_id=a.teacher_id,teacher_name=_teacher_name(db,a),title=a.title,publication_status=a.publication_status,instructions=a.instructions,brief=a.brief_json,due_date=a.due_date,is_final_project=a.is_final_project,submissions_count=int(db.scalar(select(func.count(AssignmentSubmissionRecord.id)).where(AssignmentSubmissionRecord.assignment_id==a.id)) or 0),created_at=a.created_at,can_manage=a.teacher_id==tenant.user.id and not tenant.support_mode,delete_blocked_reason=_delete_blocked_reason(db,a))
def due_date_label(org:OrganizationRecord,due_date:datetime)->str:
    """Show a deadline in the school's time zone, as students read it."""
    try: zone=ZoneInfo(org.timezone or "UTC")
    except (ZoneInfoNotFoundError,ValueError): zone=UTC
    return current_utc(due_date).astimezone(zone).strftime("%d/%m/%Y %H:%M")
def _event_context(db,a):
    return {"assignment_title":a.title,"session_label":_session_label(db,a.session_id),"due_at":due_date_label(db.get(OrganizationRecord,a.organization_id),a.due_date)}
def _student_view(db,a,e,s,now):
    status = "reviewed" if s and s.is_reviewed else "submitted" if s else "late" if _utc(now) > _utc(a.due_date) else "pending"
    session = db.get(FormationSessionRecord, a.session_id)
    formation = db.get(FormationRecord, session.formation_id)
    day = db.get(SessionCourseDayRecord, a.course_day_id) if a.course_day_id else None
    locked = not guided_activity_available(formation, session, day=day, now=now)
    available_at = None
    if dashboard_type(formation) == "guided":
        available_at = session_starts_at(session)
        if day is not None:
            available_at = max(available_at, current_utc(day.scheduled_at))
    linked_gate = linked_lesson_gate(db, formation, session, "assignment", a.id, now=now)
    if linked_gate is not None:
        linked_opening, linked_available = linked_gate
        if linked_opening is not None:
            available_at = max(available_at, linked_opening) if available_at else linked_opening
        locked = locked or not linked_available
    return StudentAssignmentRead(
        id=a.id,
        enrollment_id=e.id,
        session_id=a.session_id,
        session_label=session.label,
        formation_title=formation.title,
        teacher_name=_teacher_name(db, a),
        title=a.title,
        instructions="" if locked else a.instructions,
        brief=None if locked else a.brief_json,
        due_date=a.due_date,
        is_final_project=a.is_final_project,
        is_locked=locked,
        available_at=available_at,
        student_status=status,
        submitted_at=s.submitted_at if s else None,
        file_url=s.file_url if s else None,
        is_reviewed=s.is_reviewed if s else False,
        review_score=s.review_score if s else None,
        review_max_score=s.review_max_score if s else 20,
        comment_count=_count_comments(db, a.id, e.id),
        submissions_closed=guided_work_closed(formation, session, now=now),
    )

def assignment_open_for_students(db,session,formation,a,*,now=None):
    day = db.get(SessionCourseDayRecord, a.course_day_id) if a.course_day_id else None
    linked_gate = linked_lesson_gate(db, formation, session, "assignment", a.id, now=now)
    return guided_activity_available(formation, session, day=day, now=now) and (linked_gate is None or linked_gate[1])

def _student_assignment_open(db,tenant,a,now=None):
    session = _session(db, tenant, a.session_id)
    return assignment_open_for_students(db, session, db.get(FormationRecord, session.formation_id), a, now=now)

def list_teacher_assignments(db:Session,tenant:TenantContext,sid:int):
    _session(db,tenant,sid)
    if not _teacher_assigned(db,tenant,sid): raise HTTPException(403,"Cette session ne vous est pas affectée.")
    return [_teacher_view(db,tenant,a) for a in db.scalars(select(AssignmentRecord).where(AssignmentRecord.organization_id==tenant.organization_id,AssignmentRecord.session_id==sid).order_by(AssignmentRecord.due_date)).all()]

def create_assignment(db:Session,tenant:TenantContext,sid:int,p:AssignmentCreate):
    s=_session(db,tenant,sid)
    if not _teacher_assigned(db,tenant,sid): raise HTTPException(403,"Cette session ne vous est pas affectée.")
    if s.status in {"cancelled","completed"}: raise HTTPException(409,"Cette session n'accepte plus de nouveaux devoirs.")
    day=_own_course_day(db,tenant,sid,p.course_day_id) if p.course_day_id else None
    _check_due_date(s,day,p.due_date)
    a=AssignmentRecord(organization_id=tenant.organization_id,session_id=sid,course_day_id=p.course_day_id,teacher_id=tenant.user.id,title=p.title.strip(),publication_status="draft",instructions=p.instructions.strip(),brief_json=p.brief.model_dump() if p.brief else None,due_date=p.due_date,is_final_project=p.is_final_project)
    db.add(a); db.commit(); db.refresh(a); return _teacher_view(db,tenant,a)

def release_assignment(db:Session,org:OrganizationRecord,a:AssignmentRecord):
    """Make a draft visible to the students and tell them, only the first time."""
    if a.publication_status=="published": return
    a.publication_status="published"
    queue_session_students_event(db,org=org,session_id=a.session_id,event_key="student.assignment.created",context=_event_context(db,a))

def publish_assignment(db:Session,tenant:TenantContext,aid:int):
    a=_owned_assignment(db,tenant,aid)
    if _session(db,tenant,a.session_id).status in {"cancelled","completed"}: raise HTTPException(409,"Cette session n'accepte plus de nouveaux devoirs.")
    release_assignment(db,tenant.organization,a)
    db.commit(); db.refresh(a); return _teacher_view(db,tenant,a)

def update_assignment(db:Session,tenant:TenantContext,aid:int,p:AssignmentUpdate):
    a=_owned_assignment(db,tenant,aid)
    s=_session(db,tenant,a.session_id)
    day_id=p.course_day_id if "course_day_id" in p.model_fields_set else a.course_day_id
    due=p.due_date or a.due_date
    day_changed=day_id!=a.course_day_id
    day=None
    if day_id: day=_own_course_day(db,tenant,a.session_id,day_id) if day_changed else db.get(SessionCourseDayRecord,day_id)
    if day_changed or _utc(due)!=_utc(a.due_date): _check_due_date(s,day,due)
    if is_frozen_requirement(db,a.session_id,"final_project_ids" if a.is_final_project else "assignment_ids",a.id):
        kind_changed=p.is_final_project is not None and p.is_final_project!=a.is_final_project
        if day_changed or _utc(due)!=_utc(a.due_date) or kind_changed: raise HTTPException(409,FROZEN_MESSAGE+" Pour un devoir figé : le titre, les consignes et le texte de la fiche TP.")
        if "brief" in p.model_fields_set and _rubric(a.brief_json)!=_rubric(p.brief.model_dump() if p.brief else None): raise HTTPException(409,"La structure et le barème du TP sont figés : créez un nouveau devoir pour les changer.")
    before=(a.title,a.instructions,a.brief_json,_utc(a.due_date),a.course_day_id,a.is_final_project)
    if p.title is not None: a.title=p.title.strip()
    if p.instructions is not None: a.instructions=p.instructions.strip()
    if "brief" in p.model_fields_set: a.brief_json=p.brief.model_dump() if p.brief else None
    if p.is_final_project is not None: a.is_final_project=p.is_final_project
    a.course_day_id=day_id; a.due_date=due
    if a.publication_status=="published" and before!=(a.title,a.instructions,a.brief_json,_utc(a.due_date),a.course_day_id,a.is_final_project):
        queue_session_students_event(db,org=tenant.organization,session_id=a.session_id,event_key="student.assignment.updated",context=_event_context(db,a))
    db.commit(); db.refresh(a); return _teacher_view(db,tenant,a)

def _rubric(brief):
    if not brief: return None
    return (len(brief.get("deliverables",[])),len(brief.get("steps",[])),tuple(round(float(item.get("points",0)),2) for item in brief.get("evaluation_criteria",[])))

def delete_assignment(db:Session,tenant:TenantContext,aid:int):
    a=_owned_assignment(db,tenant,aid)
    reason=_delete_blocked_reason(db,a)
    if reason: raise HTTPException(409,reason)
    db.delete(a); db.commit()

def list_student_assignments(db:Session,tenant:TenantContext):
    if not tenant.has_role("student"): raise HTTPException(403,"Accès étudiant requis.")
    ens=list(db.scalars(select(EnrollmentRecord).where(EnrollmentRecord.organization_id==tenant.organization_id,EnrollmentRecord.student_id==tenant.user.id,EnrollmentRecord.status.in_(["active","completed"]))).all())
    now=datetime.now(UTC); out=[]
    for e in ens:
        for a in db.scalars(select(AssignmentRecord).where(AssignmentRecord.organization_id==tenant.organization_id,AssignmentRecord.session_id==e.session_id,AssignmentRecord.publication_status=="published").order_by(AssignmentRecord.due_date)).all():
            sub=db.scalar(select(AssignmentSubmissionRecord).where(AssignmentSubmissionRecord.organization_id==tenant.organization_id,AssignmentSubmissionRecord.assignment_id==a.id,AssignmentSubmissionRecord.enrollment_id==e.id))
            out.append(_student_view(db,a,e,sub,now))
    return sorted(out,key=lambda x:x.due_date)

def submit_assignment(db:Session,tenant:TenantContext,aid:int,p:AssignmentSubmit):
    a=_published_assignment(db,tenant,aid); e=_enrollment(db,tenant,a.session_id)
    if not e: raise HTTPException(403,"Vous n'êtes pas inscrit à cette session.")
    now=datetime.now(UTC)
    session=_session(db,tenant,a.session_id)
    if guided_work_closed(db.get(FormationRecord,session.formation_id),session,now=now): raise HTTPException(409,WORK_CLOSED_MESSAGE)
    if not _student_assignment_open(db,tenant,a,now): raise HTTPException(409,"Ce devoir n'est pas encore disponible.")
    validate_submission_asset(p.file_url, tenant.organization_id, tenant.user.id)
    sub=db.scalar(select(AssignmentSubmissionRecord).where(AssignmentSubmissionRecord.organization_id==tenant.organization_id,AssignmentSubmissionRecord.assignment_id==aid,AssignmentSubmissionRecord.enrollment_id==e.id))
    first_submission = sub is None
    if sub:
        sub.file_url=p.file_url; sub.submitted_at=now; sub.is_reviewed=False; sub.review_score=None; sub.review_max_score=20
    else:
        sub=AssignmentSubmissionRecord(organization_id=tenant.organization_id,assignment_id=aid,enrollment_id=e.id,file_url=p.file_url,submitted_at=now)
        db.add(sub)
    complete_activity_lessons(db, organization_id=tenant.organization_id, session_id=a.session_id, enrollment_id=e.id, activity_type="assignment", activity_id=a.id)
    db.execute(
        delete(GradeRecord).where(
            GradeRecord.organization_id == tenant.organization_id,
            GradeRecord.enrollment_id == e.id,
            GradeRecord.source_type == "assignment",
            GradeRecord.source_id == a.id,
        )
    )
    if a.teacher_id:
        notify_user(
            db, organization_id=tenant.organization_id, user_id=a.teacher_id,
            event_key=f"assignment.submitted:{aid}:{e.id}:{now.isoformat()}",
            audience="teacher",
            title="Devoir remis", message=f"{tenant.user.full_name} a remis « {a.title} ».",
            category="assignment", action_label="Voir les devoirs",
            action_path="/app/teacher/assignments",
        )
        if first_submission:
            email_new_submission(
                db, org=tenant.organization, teacher_id=a.teacher_id, student=tenant.user,
                assignment_title=a.title, session_label=_session_label(db, a.session_id),
            )
    db.commit(); db.refresh(sub); return _student_view(db,a,e,sub,now)

def list_submissions(db,tenant,aid):
    a=_assignment(db,tenant,aid)
    if not _teacher_assigned(db,tenant,a.session_id): raise HTTPException(403,"Cette session ne vous est pas affectée.")
    rows=db.scalars(select(AssignmentSubmissionRecord).where(AssignmentSubmissionRecord.organization_id==tenant.organization_id,AssignmentSubmissionRecord.assignment_id==aid).order_by(AssignmentSubmissionRecord.submitted_at)).all()
    out=[]
    for s in rows:
        e=db.get(EnrollmentRecord,s.enrollment_id); u=db.get(UserRecord,e.student_id) if e else None
        out.append(SubmissionRead(id=s.id,enrollment_id=s.enrollment_id,student_name=u.full_name if u else "-",file_url=s.file_url,submitted_at=s.submitted_at,is_reviewed=s.is_reviewed,review_score=s.review_score,review_max_score=s.review_max_score,comment_count=_count_comments(db,aid,s.enrollment_id)))
    return out

def review_submission(db,tenant,aid,sid,p:ReviewSubmission):
    a=_assignment(db,tenant,aid)
    if a.teacher_id!=tenant.user.id: raise HTTPException(403,"La correction est réservée au professeur propriétaire du devoir.")
    s=db.scalar(select(AssignmentSubmissionRecord).where(AssignmentSubmissionRecord.id==sid,AssignmentSubmissionRecord.organization_id==tenant.organization_id,AssignmentSubmissionRecord.assignment_id==aid))
    if not s: raise HTTPException(404,"Soumission introuvable.")
    s.review_score=p.review_score; s.review_max_score=20; s.is_reviewed=True
    upsert_grade(
        db,
        organization_id=tenant.organization_id,
        session_id=a.session_id,
        enrollment_id=s.enrollment_id,
        teacher_id=a.teacher_id,
        source_type="assignment",
        source_id=a.id,
        label=("Projet final : " if a.is_final_project else "Devoir : ") + a.title,
        score=p.review_score,
        max_score=20,
        note="Note issue de la correction du devoir.",
    )
    enrollment = db.get(EnrollmentRecord, s.enrollment_id)
    student = db.get(UserRecord, enrollment.student_id) if enrollment else None
    if student:
        queue_school_event(
            db,
            org=tenant.organization,
            user=student,
            event_key="student.assignment.reviewed",
            context={
                "assignment_title": a.title,
                "score_label": f"{p.review_score}/20",
            },
        )
        notify_user(
            db, organization_id=tenant.organization_id, user_id=student.id,
            event_key=f"assignment.reviewed:{s.id}:{p.review_score}",
            audience="student",
            title="Devoir corrigé", message=f"Votre devoir « {a.title} » a été corrigé : {p.review_score}/20.",
            category="assignment", tone="success", action_label="Voir mes résultats",
            action_path="/app/student/results",
        )
    db.commit()
    return next(x for x in list_submissions(db,tenant,aid) if x.id==sid)

def _thread_access(db,tenant,a,enrollment_id):
    e=db.get(EnrollmentRecord,enrollment_id)
    if not e or e.organization_id!=tenant.organization_id or e.session_id!=a.session_id: raise HTTPException(404,"Inscription introuvable.")
    if tenant.has_role("student") and e.student_id==tenant.user.id: return "student"
    if tenant.has_role("teacher") and _teacher_assigned(db,tenant,a.session_id):
        if a.teacher_id!=tenant.user.id: raise HTTPException(403,"Les échanges de ce devoir sont réservés au professeur propriétaire.")
        return "teacher"
    raise HTTPException(403,"Accès refusé.")

def _require_student_thread_open(db,tenant,a):
    if a.publication_status!="published": raise HTTPException(404,"Devoir introuvable.")
    if not _student_assignment_open(db,tenant,a): raise HTTPException(409,"Ce devoir n'est pas encore disponible.")

def list_comments(db,tenant,aid,enrollment_id):
    a=_assignment(db,tenant,aid); role=_thread_access(db,tenant,a,enrollment_id)
    if role=="student": _require_student_thread_open(db,tenant,a)
    rows=db.scalars(select(AssignmentCommentRecord).where(AssignmentCommentRecord.organization_id==tenant.organization_id,AssignmentCommentRecord.assignment_id==aid,AssignmentCommentRecord.enrollment_id==enrollment_id).order_by(AssignmentCommentRecord.created_at)).all()
    return [CommentRead(id=x.id,assignment_id=aid,enrollment_id=enrollment_id,author_role=x.author_role,author_name=(db.get(UserRecord,x.author_user_id).full_name if db.get(UserRecord,x.author_user_id) else "-"),body=x.body,attachment_url=x.attachment_url,created_at=x.created_at) for x in rows]

def add_comment(db,tenant,aid,enrollment_id,p:CommentCreate):
    a=_assignment(db,tenant,aid); role=_thread_access(db,tenant,a,enrollment_id)
    if role=="student": _require_student_thread_open(db,tenant,a)
    if not p.body.strip() and not p.attachment_url: raise HTTPException(422,"Ajoutez un message ou une pièce jointe.")
    x=AssignmentCommentRecord(organization_id=tenant.organization_id,assignment_id=aid,enrollment_id=enrollment_id,author_user_id=tenant.user.id,author_role=role,body=p.body.strip(),attachment_url=p.attachment_url)
    db.add(x); db.commit(); db.refresh(x); return list_comments(db,tenant,aid,enrollment_id)[-1]
