from datetime import UTC,date,datetime
from io import BytesIO
import asyncio
from pathlib import Path
import pytest
from fastapi import HTTPException, UploadFile
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.db.base import Base
from app.models.entities import *
from app.schemas.assignments import *
from app.services.assignments import *
from app.services.membership_roles import replace_effective_roles
from app.services.tenancy import resolve_tenant_context
from app.services.assets import store_assignment_asset, store_submission_asset
from app.api.routes.assignments import download_legacy_submission, download_resource_asset, download_submission_asset
from app.core.config import settings
from app.main import PublicUploads

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
 asset=asyncio.run(store_submission_asset(UploadFile(file=BytesIO(b"test work"),filename="work.pdf"),o.id,s.id))
 path=Path(__file__).resolve().parents[1]/"private_uploads"/"schools"/str(o.id)/"assignments"/str(s.id)/asset["public_url"].rsplit("/",1)[-1]
 try:
  sub=submit_assignment(db,ctx(db,o,s),a.id,AssignmentSubmit(file_url=asset["public_url"])); assert sub.student_status=="submitted"
  rows=list_submissions(db,ctx(db,o,t),a.id); assert len(rows)==1
  reviewed=review_submission(db,ctx(db,o,t),a.id,rows[0].id,ReviewSubmission(review_score=16)); assert reviewed.review_score==16 and reviewed.is_reviewed
  assert list_student_assignments(db,ctx(db,o,s))[0].student_status=="reviewed"
 finally:
  path.unlink(missing_ok=True)


def test_submission_file_requires_student_or_own_teacher(monkeypatch):
 db=dbx();o,t,s,se=seed(db)
 monkeypatch.setattr(settings,"storage_provider","local")
 monkeypatch.setattr(settings,"environment","development")
 a=create_assignment(db,ctx(db,o,t),se.id,AssignmentCreate(title="Projet",due_date=datetime(2026,10,20,18,tzinfo=UTC)))
 with pytest.raises(HTTPException) as invalid:
  submit_assignment(db,ctx(db,o,s),a.id,AssignmentSubmit(file_url="https://public.example/work.pdf"))
 assert invalid.value.status_code==422
 upload=UploadFile(file=BytesIO(b"private homework"),filename="work.pdf")
 asset=asyncio.run(store_submission_asset(upload,o.id,s.id))
 path=None
 try:
  submit_assignment(db,ctx(db,o,s),a.id,AssignmentSubmit(file_url=asset["public_url"]))
  filename=asset["public_url"].rsplit("/",1)[-1]
  response=download_submission_asset(s.id,filename,db,ctx(db,o,t))
  path=Path(response.path)
  assert path.read_bytes()==b"private homework"
  stranger=UserRecord(email="stranger@test.dev",full_name="Stranger",status="active")
  db.add(stranger);db.flush()
  member=OrganizationMemberRecord(organization_id=o.id,user_id=stranger.id,role="student",status="active")
  db.add(member);db.flush();replace_effective_roles(db,member,{"student"});db.commit()
  with pytest.raises(HTTPException) as exc:
   download_submission_asset(s.id,filename,db,ctx(db,o,stranger))
  assert exc.value.status_code==403
 finally:
  if path: path.unlink(missing_ok=True)


def test_teacher_resource_download_checks_session_access(monkeypatch):
 db=dbx();o,t,s,se=seed(db)
 monkeypatch.setattr(settings,"storage_provider","local")
 monkeypatch.setattr(settings,"environment","development")
 asset=asyncio.run(store_assignment_asset(UploadFile(file=BytesIO(b"course notes"),filename="notes.pdf"),o.id))
 filename=asset["public_url"].rsplit("/",1)[-1]
 path=Path(__file__).resolve().parents[1]/"private_uploads"/"schools"/str(o.id)/"resources"/filename
 try:
  assert path.read_bytes()==b"course notes"
  assert not (Path(__file__).resolve().parents[1]/"uploads"/"schools"/str(o.id)/"resources"/filename).exists()
  resource=ResourceRecord(organization_id=o.id,session_id=se.id,teacher_id=t.id,title="Notes",resource_type="pdf",url=asset["public_url"])
  db.add(resource);db.commit()
  assert Path(download_resource_asset(filename,db,ctx(db,o,t)).path).read_bytes()==b"course notes"
  with pytest.raises(HTTPException) as unpublished:
   download_resource_asset(filename,db,ctx(db,o,s))
  assert unpublished.value.status_code==403
  resource.published_at=datetime.now(UTC);db.commit()
  assert Path(download_resource_asset(filename,db,ctx(db,o,s)).path).read_bytes()==b"course notes"
  stranger=UserRecord(email="resource-stranger@test.dev",full_name="Stranger",status="active")
  db.add(stranger);db.flush()
  member=OrganizationMemberRecord(organization_id=o.id,user_id=stranger.id,role="student",status="active")
  db.add(member);db.flush();replace_effective_roles(db,member,{"student"});db.commit()
  with pytest.raises(HTTPException) as forbidden:
   download_resource_asset(filename,db,ctx(db,o,stranger))
  assert forbidden.value.status_code==403
  other_teacher=UserRecord(email="resource-teacher@test.dev",full_name="Other teacher",status="active")
  db.add(other_teacher);db.flush()
  teacher_member=OrganizationMemberRecord(organization_id=o.id,user_id=other_teacher.id,role="teacher",status="active")
  db.add(teacher_member);db.flush();replace_effective_roles(db,teacher_member,{"teacher"});db.commit()
  with pytest.raises(HTTPException) as other_forbidden:
   download_resource_asset(filename,db,ctx(db,o,other_teacher))
  assert other_forbidden.value.status_code==403
 finally:
  path.unlink(missing_ok=True)


def test_legacy_teacher_resource_is_available_through_authorized_route(monkeypatch):
 db=dbx();o,t,s,se=seed(db)
 monkeypatch.setattr(settings,"storage_provider","local")
 filename="b"*32+".pdf"
 path=Path(__file__).resolve().parents[1]/"uploads"/"schools"/str(o.id)/"assignments"/filename
 path.parent.mkdir(parents=True,exist_ok=True)
 path.write_bytes(b"legacy course notes")
 try:
  db.add(ResourceRecord(organization_id=o.id,session_id=se.id,teacher_id=t.id,title="Ancien support",resource_type="pdf",url=f"https://old-storage.example/schools/{o.id}/assignments/{filename}",published_at=datetime.now(UTC)))
  db.commit()
  assert Path(download_resource_asset(filename,db,ctx(db,o,s)).path).read_bytes()==b"legacy course notes"
 finally:
  path.unlink(missing_ok=True)


def test_legacy_submission_is_available_only_through_authorized_route(monkeypatch):
 db=dbx();o,t,s,se=seed(db)
 monkeypatch.setattr(settings,"storage_provider","local")
 a=create_assignment(db,ctx(db,o,t),se.id,AssignmentCreate(title="Ancien devoir",due_date=datetime(2026,10,20,18,tzinfo=UTC)))
 filename="a"*32+".pdf"
 path=Path(__file__).resolve().parents[1]/"uploads"/"schools"/str(o.id)/"assignments"/filename
 path.parent.mkdir(parents=True,exist_ok=True)
 path.write_bytes(b"old private work")
 try:
  enrollment=db.query(EnrollmentRecord).filter_by(organization_id=o.id,student_id=s.id,session_id=se.id).one()
  db.add(AssignmentSubmissionRecord(organization_id=o.id,assignment_id=a.id,enrollment_id=enrollment.id,file_url=f"{settings.backend_public_url}/uploads/schools/{o.id}/assignments/{filename}",submitted_at=datetime.now(UTC)))
  db.commit()
  assert asyncio.run(PublicUploads(directory=path.parents[3]).get_response(f"schools/{o.id}/assignments/{filename}",{})).status_code==404
  assert Path(download_legacy_submission(filename,db,ctx(db,o,t)).path).read_bytes()==b"old private work"
  stranger=UserRecord(email="other-legacy@test.dev",full_name="Other",status="active")
  db.add(stranger);db.flush()
  member=OrganizationMemberRecord(organization_id=o.id,user_id=stranger.id,role="student",status="active")
  db.add(member);db.flush();replace_effective_roles(db,member,{"student"});db.commit()
  with pytest.raises(HTTPException) as exc:
   download_legacy_submission(filename,db,ctx(db,o,stranger))
  assert exc.value.status_code==403
 finally:
  path.unlink(missing_ok=True)

def test_student_cannot_submit_after_deadline():
 db=dbx();o,t,s,se=seed(db)
 a=create_assignment(db,ctx(db,o,t),se.id,AssignmentCreate(title="Projet",due_date=datetime(2026,10,1,18,tzinfo=UTC)))
 with pytest.raises(HTTPException) as exc: submit_assignment(db,ctx(db,o,s),a.id,AssignmentSubmit(file_url="x"))
 assert exc.value.status_code==400
