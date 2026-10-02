from datetime import UTC,date,datetime
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.db.base import Base
from app.models.entities import *
from app.schemas.assignments import *
from app.services.assignments import *
from app.services.membership_roles import replace_effective_roles
from app.services.tenancy import resolve_tenant_context

def dbx():
 e=create_engine("sqlite+pysqlite:///:memory:",connect_args={"check_same_thread":False}); Base.metadata.create_all(e); return Session(e,expire_on_commit=False)
def seed(db):
 org=OrganizationRecord(name="S",slug="s"); t=UserRecord(email="t@x.dev",full_name="Teacher",status="active"); s=UserRecord(email="s@x.dev",full_name="Student",status="active"); db.add_all([org,t,s]);db.flush()
 mt=OrganizationMemberRecord(organization_id=org.id,user_id=t.id,role="teacher",status="active"); ms=OrganizationMemberRecord(organization_id=org.id,user_id=s.id,role="student",status="active");db.add_all([mt,ms]);db.flush();replace_effective_roles(db,mt,{"teacher"});replace_effective_roles(db,ms,{"student"})
 f=FormationRecord(organization_id=org.id,slug="f",title="F");db.add(f);db.flush(); se=FormationSessionRecord(organization_id=org.id,formation_id=f.id,label="C",start_date=date(2026,10,1),end_date=date(2026,10,31),status="open");db.add(se);db.flush()
 db.add_all([SessionTeacherRecord(organization_id=org.id,session_id=se.id,teacher_id=t.id,role="principal"),EnrollmentRecord(organization_id=org.id,session_id=se.id,student_id=s.id,status="active")]);db.commit()
 return org,t,s,se
def ctx(db,o,u): return resolve_tenant_context(db,user=u,organization_id=o.id)

def test_assignment_submission_review_flow():
 db=dbx();o,t,s,se=seed(db)
 a=create_assignment(db,ctx(db,o,t),se.id,AssignmentCreate(title="Projet",instructions="Créer",due_date=datetime(2026,10,20,18,tzinfo=UTC)))
 assert a.teacher_name=="Teacher"
 sa=list_student_assignments(db,ctx(db,o,s))[0]; assert sa.student_status=="pending"
 sub=submit_assignment(db,ctx(db,o,s),a.id,AssignmentSubmit(file_url="https://files.test/work.pdf")); assert sub.student_status=="submitted"
 rows=list_submissions(db,ctx(db,o,t),a.id); assert len(rows)==1
 reviewed=review_submission(db,ctx(db,o,t),a.id,rows[0].id,ReviewSubmission(review_score=16)); assert reviewed.review_score==16 and reviewed.is_reviewed
 assert list_student_assignments(db,ctx(db,o,s))[0].student_status=="reviewed"

def test_student_cannot_submit_after_deadline():
 db=dbx();o,t,s,se=seed(db)
 a=create_assignment(db,ctx(db,o,t),se.id,AssignmentCreate(title="Projet",due_date=datetime(2026,10,1,18,tzinfo=UTC)))
 with pytest.raises(HTTPException) as exc: submit_assignment(db,ctx(db,o,s),a.id,AssignmentSubmit(file_url="x"))
 assert exc.value.status_code==400
