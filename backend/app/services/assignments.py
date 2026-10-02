from datetime import UTC, datetime, time
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models.entities import AssignmentCommentRecord, AssignmentRecord, AssignmentSubmissionRecord, EnrollmentRecord, FormationRecord, FormationSessionRecord, SessionCourseDayRecord, SessionTeacherRecord, UserRecord
from app.schemas.assignments import *
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
def _count_comments(db,a,e): return int(db.scalar(select(func.count(AssignmentCommentRecord.id)).where(AssignmentCommentRecord.assignment_id==a,AssignmentCommentRecord.enrollment_id==e)) or 0)
def _teacher_name(db,a): return db.get(UserRecord,a.teacher_id).full_name if a.teacher_id and db.get(UserRecord,a.teacher_id) else None
def _formation_title(db,sid):
    row=db.execute(select(FormationRecord.title).join(FormationSessionRecord,FormationSessionRecord.formation_id==FormationRecord.id).where(FormationSessionRecord.id==sid)).scalar_one_or_none()
    return row or ""
def _session_label(db,sid): return db.get(FormationSessionRecord,sid).label
def _teacher_view(db,a):
    return AssignmentRead(id=a.id,session_id=a.session_id,course_day_id=a.course_day_id,teacher_id=a.teacher_id,teacher_name=_teacher_name(db,a),title=a.title,instructions=a.instructions,due_date=a.due_date,is_final_project=a.is_final_project,submissions_count=int(db.scalar(select(func.count(AssignmentSubmissionRecord.id)).where(AssignmentSubmissionRecord.assignment_id==a.id)) or 0),created_at=a.created_at)
def _student_view(db,a,e,s,now):
    st="reviewed" if s and s.is_reviewed else "submitted" if s else "late" if _utc(now)>_utc(a.due_date) else "pending"
    return StudentAssignmentRead(id=a.id,enrollment_id=e.id,session_id=a.session_id,session_label=_session_label(db,a.session_id),formation_title=_formation_title(db,a.session_id),teacher_name=_teacher_name(db,a),title=a.title,instructions=a.instructions,due_date=a.due_date,is_final_project=a.is_final_project,student_status=st,submitted_at=s.submitted_at if s else None,file_url=s.file_url if s else None,is_reviewed=s.is_reviewed if s else False,review_score=s.review_score if s else None,review_max_score=s.review_max_score if s else 20,comment_count=_count_comments(db,a.id,e.id))

def list_teacher_assignments(db:Session,tenant:TenantContext,sid:int):
    _session(db,tenant,sid)
    if not _teacher_assigned(db,tenant,sid): raise HTTPException(403,"Cette session ne vous est pas affectée.")
    return [_teacher_view(db,a) for a in db.scalars(select(AssignmentRecord).where(AssignmentRecord.organization_id==tenant.organization_id,AssignmentRecord.session_id==sid).order_by(AssignmentRecord.due_date)).all()]

def create_assignment(db:Session,tenant:TenantContext,sid:int,p:AssignmentCreate):
    s=_session(db,tenant,sid)
    if not _teacher_assigned(db,tenant,sid): raise HTTPException(403,"Cette session ne vous est pas affectée.")
    if s.status in {"cancelled","completed"}: raise HTTPException(409,"Cette session n'accepte plus de nouveaux devoirs.")
    day=None
    if p.course_day_id:
        day=db.scalar(select(SessionCourseDayRecord).where(SessionCourseDayRecord.id==p.course_day_id,SessionCourseDayRecord.organization_id==tenant.organization_id,SessionCourseDayRecord.session_id==sid))
        if not day: raise HTTPException(422,"Le créneau ne correspond pas à cette session.")
        if day.teacher_id!=tenant.user.id: raise HTTPException(403,"Vous ne pouvez rattacher un devoir qu'à l'un de vos créneaux.")
        if _utc(p.due_date)<_utc(day.scheduled_at): raise HTTPException(422,"La date limite doit être postérieure au créneau.")
    start=datetime.combine(s.start_date,time.min); end=datetime.combine(s.end_date,time.max)
    due=_utc(p.due_date)
    if due<start or due>end: raise HTTPException(422,"La date limite doit rester dans les dates de la session.")
    a=AssignmentRecord(organization_id=tenant.organization_id,session_id=sid,course_day_id=p.course_day_id,teacher_id=tenant.user.id,title=p.title.strip(),instructions=p.instructions.strip(),due_date=p.due_date,is_final_project=p.is_final_project)
    db.add(a); db.commit(); db.refresh(a); return _teacher_view(db,a)

def list_student_assignments(db:Session,tenant:TenantContext):
    if not tenant.has_role("student"): raise HTTPException(403,"Accès étudiant requis.")
    ens=list(db.scalars(select(EnrollmentRecord).where(EnrollmentRecord.organization_id==tenant.organization_id,EnrollmentRecord.student_id==tenant.user.id,EnrollmentRecord.status.in_(["active","completed"]))).all())
    now=datetime.now(UTC); out=[]
    for e in ens:
        for a in db.scalars(select(AssignmentRecord).where(AssignmentRecord.organization_id==tenant.organization_id,AssignmentRecord.session_id==e.session_id).order_by(AssignmentRecord.due_date)).all():
            sub=db.scalar(select(AssignmentSubmissionRecord).where(AssignmentSubmissionRecord.organization_id==tenant.organization_id,AssignmentSubmissionRecord.assignment_id==a.id,AssignmentSubmissionRecord.enrollment_id==e.id))
            out.append(_student_view(db,a,e,sub,now))
    return sorted(out,key=lambda x:x.due_date)

def submit_assignment(db:Session,tenant:TenantContext,aid:int,p:AssignmentSubmit):
    a=_assignment(db,tenant,aid); e=_enrollment(db,tenant,a.session_id)
    if not e: raise HTTPException(403,"Vous n'êtes pas inscrit à cette session.")
    now=datetime.now(UTC)
    if _utc(now)>_utc(a.due_date): raise HTTPException(400,"La date limite de remise est dépassée.")
    sub=db.scalar(select(AssignmentSubmissionRecord).where(AssignmentSubmissionRecord.organization_id==tenant.organization_id,AssignmentSubmissionRecord.assignment_id==aid,AssignmentSubmissionRecord.enrollment_id==e.id))
    if sub:
        sub.file_url=p.file_url; sub.submitted_at=now; sub.is_reviewed=False; sub.review_score=None; sub.review_max_score=20
    else:
        sub=AssignmentSubmissionRecord(organization_id=tenant.organization_id,assignment_id=aid,enrollment_id=e.id,file_url=p.file_url,submitted_at=now)
        db.add(sub)
    db.commit(); db.refresh(sub); return _student_view(db,a,e,sub,now)

def list_submissions(db,tenant,aid):
    a=_assignment(db,tenant,aid)
    if not _teacher_assigned(db,tenant,a.session_id): raise HTTPException(403,"Cette session ne vous est pas affectée.")
    rows=db.scalars(select(AssignmentSubmissionRecord).where(AssignmentSubmissionRecord.organization_id==tenant.organization_id,AssignmentSubmissionRecord.assignment_id==aid).order_by(AssignmentSubmissionRecord.submitted_at)).all()
    out=[]
    for s in rows:
        e=db.get(EnrollmentRecord,s.enrollment_id); u=db.get(UserRecord,e.student_id) if e else None
        out.append(SubmissionRead(id=s.id,enrollment_id=s.enrollment_id,student_name=u.full_name if u else "—",file_url=s.file_url,submitted_at=s.submitted_at,is_reviewed=s.is_reviewed,review_score=s.review_score,review_max_score=s.review_max_score,comment_count=_count_comments(db,aid,s.enrollment_id)))
    return out

def review_submission(db,tenant,aid,sid,p:ReviewSubmission):
    a=_assignment(db,tenant,aid)
    if a.teacher_id!=tenant.user.id: raise HTTPException(403,"La correction est réservée au professeur propriétaire du devoir.")
    s=db.scalar(select(AssignmentSubmissionRecord).where(AssignmentSubmissionRecord.id==sid,AssignmentSubmissionRecord.organization_id==tenant.organization_id,AssignmentSubmissionRecord.assignment_id==aid))
    if not s: raise HTTPException(404,"Soumission introuvable.")
    s.review_score=p.review_score; s.review_max_score=20; s.is_reviewed=True; db.commit()
    return next(x for x in list_submissions(db,tenant,aid) if x.id==sid)

def _thread_access(db,tenant,a,enrollment_id):
    e=db.get(EnrollmentRecord,enrollment_id)
    if not e or e.organization_id!=tenant.organization_id or e.session_id!=a.session_id: raise HTTPException(404,"Inscription introuvable.")
    if tenant.has_role("student") and e.student_id==tenant.user.id: return "student"
    if tenant.has_role("teacher") and _teacher_assigned(db,tenant,a.session_id):
        if a.teacher_id!=tenant.user.id: raise HTTPException(403,"Les échanges de ce devoir sont réservés au professeur propriétaire.")
        return "teacher"
    raise HTTPException(403,"Accès refusé.")

def list_comments(db,tenant,aid,enrollment_id):
    a=_assignment(db,tenant,aid); _thread_access(db,tenant,a,enrollment_id)
    rows=db.scalars(select(AssignmentCommentRecord).where(AssignmentCommentRecord.organization_id==tenant.organization_id,AssignmentCommentRecord.assignment_id==aid,AssignmentCommentRecord.enrollment_id==enrollment_id).order_by(AssignmentCommentRecord.created_at)).all()
    return [CommentRead(id=x.id,assignment_id=aid,enrollment_id=enrollment_id,author_role=x.author_role,author_name=(db.get(UserRecord,x.author_user_id).full_name if db.get(UserRecord,x.author_user_id) else "—"),body=x.body,attachment_url=x.attachment_url,created_at=x.created_at) for x in rows]

def add_comment(db,tenant,aid,enrollment_id,p:CommentCreate):
    a=_assignment(db,tenant,aid); role=_thread_access(db,tenant,a,enrollment_id)
    if not p.body.strip() and not p.attachment_url: raise HTTPException(422,"Ajoutez un message ou une pièce jointe.")
    x=AssignmentCommentRecord(organization_id=tenant.organization_id,assignment_id=aid,enrollment_id=enrollment_id,author_user_id=tenant.user.id,author_role=role,body=p.body.strip(),attachment_url=p.attachment_url)
    db.add(x); db.commit(); db.refresh(x); return list_comments(db,tenant,aid,enrollment_id)[-1]
