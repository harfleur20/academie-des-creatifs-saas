from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_tenant_context
from app.db.session import get_db
from app.models.entities import CertificateRecord
from app.services.academic_access import can_view_session, get_session
from app.services.assets import store_class_discussion_image
from app.schemas.academic import (
    AttendanceCourseDayRead,
    AttendanceMarkPayload,
    CertificateEligibilityRead,
    CertificateRead,
    DiscussionCreate,
    DiscussionPostRead,
    DiscussionReplyRead,
    GradeRead,
    LearningSessionRead,
    LessonVideoHeartbeatPayload,
    ProgressRead,
    QuizAttemptPayload,
    QuizCreate,
    QuizStatusUpdate,
    ResourceCreate,
    ResourceRead,
    StudentAttendanceRead,
    StudentClassRead,
    StudentQuizRead,
    TeacherPerformanceRead,
    SchoolPedagogyOverviewRead,
    TeacherQuizRead,
    TeacherQuizResultsRead,
)
from app.services.class_certificates import (
    certificate_eligibility,
    create_discussion_post,
    create_discussion_reply,
    delete_discussion_post,
    discussion_posts,
    issue_certificate,
    list_student_classes,
    verify_certificate_token,
)
from app.services.school_documents import build_certificate_pdf
from app.services.learning_progress import (
    mark_attendance,
    mark_lesson_complete,
    student_attendance,
    student_grades,
    student_progress,
    teacher_attendance,
    teacher_performance,
    list_student_learning,
    sync_lesson_video_progress,
)
from app.services.resources_quizzes import (
    create_quiz,
    create_resource,
    list_student_quizzes,
    list_student_resources,
    list_teacher_quizzes,
    list_teacher_resources,
    set_quiz_status,
    submit_quiz_attempt,
    teacher_quiz_results,
)
from app.services.school_pedagogy import school_pedagogy_overview
from app.services.tenancy import TenantContext, require_organization_roles


router = APIRouter(prefix="/academic", tags=["academic"])



@router.get(
    "/manage/overview",
    response_model=SchoolPedagogyOverviewRead,
)
def read_school_pedagogy_overview(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    require_organization_roles(tenant, "owner", "admin", "manager")
    return school_pedagogy_overview(db, tenant)


@router.get("/teacher/sessions/{session_id}/resources", response_model=list[ResourceRead])
def teacher_resources(
    session_id: int,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return list_teacher_resources(db, tenant, session_id)


@router.post(
    "/teacher/sessions/{session_id}/resources",
    response_model=ResourceRead,
    status_code=status.HTTP_201_CREATED,
)
def teacher_create_resource(
    session_id: int,
    payload: ResourceCreate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return create_resource(db, tenant, session_id, payload)


@router.get("/student/resources", response_model=list[ResourceRead])
def student_resources(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return list_student_resources(db, tenant)


@router.get("/teacher/sessions/{session_id}/quizzes", response_model=list[TeacherQuizRead])
def teacher_quizzes(
    session_id: int,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return list_teacher_quizzes(db, tenant, session_id)


@router.post(
    "/teacher/sessions/{session_id}/quizzes",
    response_model=TeacherQuizRead,
    status_code=status.HTTP_201_CREATED,
)
def teacher_create_quiz(
    session_id: int,
    payload: QuizCreate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return create_quiz(db, tenant, session_id, payload)


@router.patch("/teacher/quizzes/{quiz_id}", response_model=TeacherQuizRead)
def teacher_update_quiz_status(
    quiz_id: int,
    payload: QuizStatusUpdate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return set_quiz_status(db, tenant, quiz_id, payload.status)


@router.get(
    "/teacher/quizzes/{quiz_id}/results",
    response_model=TeacherQuizResultsRead,
)
def teacher_results(
    quiz_id: int,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return teacher_quiz_results(db, tenant, quiz_id)


@router.get("/student/quizzes", response_model=list[StudentQuizRead])
def student_quizzes(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return list_student_quizzes(db, tenant)


@router.post("/student/quizzes/{quiz_id}/attempt", response_model=StudentQuizRead)
def student_quiz_attempt(
    quiz_id: int,
    payload: QuizAttemptPayload,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return submit_quiz_attempt(db, tenant, quiz_id, payload)


@router.get("/student/learning", response_model=list[LearningSessionRead])
def student_learning(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return list_student_learning(db, tenant)


@router.post(
    "/student/lessons/{lesson_id}/complete",
    response_model=LearningSessionRead,
)
def complete_lesson(
    lesson_id: int,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return mark_lesson_complete(db, tenant, lesson_id)


@router.post(
    "/student/lessons/{lesson_id}/video-progress",
    response_model=LearningSessionRead,
)
def report_lesson_video_progress(
    lesson_id: int,
    payload: LessonVideoHeartbeatPayload,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return sync_lesson_video_progress(db, tenant, lesson_id, payload)


@router.get(
    "/teacher/sessions/{session_id}/attendance",
    response_model=list[AttendanceCourseDayRead],
)
def read_teacher_attendance(
    session_id: int,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return teacher_attendance(db, tenant, session_id)


@router.put(
    "/teacher/course-days/{course_day_id}/attendance",
    response_model=AttendanceCourseDayRead,
)
def update_teacher_attendance(
    course_day_id: int,
    payload: AttendanceMarkPayload,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return mark_attendance(db, tenant, course_day_id, payload)


@router.get("/student/attendance", response_model=list[StudentAttendanceRead])
def read_student_attendance(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return student_attendance(db, tenant)


@router.get("/student/grades", response_model=list[GradeRead])
def read_student_grades(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return student_grades(db, tenant)


@router.get("/student/progress", response_model=list[ProgressRead])
def read_student_progress(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return student_progress(db, tenant)


@router.get("/teacher/performance", response_model=TeacherPerformanceRead)
def read_teacher_performance(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return teacher_performance(db, tenant)


@router.get("/student/classes", response_model=list[StudentClassRead])
def read_student_classes(
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return list_student_classes(db, tenant)


@router.get(
    "/classes/{session_id}/discussion",
    response_model=list[DiscussionPostRead],
)
def read_class_discussion(
    session_id: int,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return discussion_posts(db, tenant, session_id)


@router.post("/classes/{session_id}/discussion/assets", status_code=status.HTTP_201_CREATED)
async def upload_class_discussion_asset(
    session_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    if tenant.support_mode:
        raise HTTPException(403, "Le mode support est en lecture seule.")
    get_session(db, tenant, session_id)
    if not can_view_session(db, tenant, session_id):
        raise HTTPException(403, "Vous n'avez pas accès à cette classe.")
    return await store_class_discussion_image(file, tenant.organization_id, session_id)


@router.post(
    "/classes/{session_id}/discussion",
    response_model=DiscussionPostRead,
    status_code=status.HTTP_201_CREATED,
)
def create_class_post(
    session_id: int,
    payload: DiscussionCreate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return create_discussion_post(db, tenant, session_id, payload)


@router.post(
    "/classes/{session_id}/discussion/{post_id}/replies",
    response_model=DiscussionReplyRead,
    status_code=status.HTTP_201_CREATED,
)
def create_class_reply(
    session_id: int,
    post_id: int,
    payload: DiscussionCreate,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return create_discussion_reply(db, tenant, session_id, post_id, payload)


@router.delete(
    "/classes/{session_id}/discussion/{post_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_class_post(
    session_id: int,
    post_id: int,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    delete_discussion_post(db, tenant, session_id, post_id)


@router.get(
    "/student/enrollments/{enrollment_id}/certificate",
    response_model=CertificateEligibilityRead,
)
def read_certificate_eligibility(
    enrollment_id: int,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return certificate_eligibility(db, tenant, enrollment_id)


@router.post(
    "/student/enrollments/{enrollment_id}/certificate",
    response_model=CertificateRead,
    status_code=status.HTTP_201_CREATED,
)
def create_certificate(
    enrollment_id: int,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    return issue_certificate(db, tenant, enrollment_id)


@router.get("/student/enrollments/{enrollment_id}/certificate.pdf")
def download_student_certificate(
    enrollment_id: int,
    db: Session = Depends(get_db),
    tenant: TenantContext = Depends(get_tenant_context),
):
    issue_certificate(db, tenant, enrollment_id)
    certificate = db.query(CertificateRecord).filter(
        CertificateRecord.organization_id == tenant.organization_id,
        CertificateRecord.enrollment_id == enrollment_id,
    ).first()
    if certificate is None:
        return Response(status_code=404)
    filename, content = build_certificate_pdf(certificate)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/certificates/{token}/download")
def download_verified_certificate(
    token: str,
    db: Session = Depends(get_db),
):
    verify_certificate_token(db, token)
    try:
        certificate_id = int(token.split(".", 1)[0])
    except (ValueError, TypeError):
        return Response(status_code=404)
    certificate = db.get(CertificateRecord, certificate_id)
    if certificate is None:
        return Response(status_code=404)
    filename, content = build_certificate_pdf(certificate)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "public, max-age=3600",
        },
    )


@router.get(
    "/certificates/verify/{token}",
    response_model=CertificateRead,
)
def verify_certificate(
    token: str,
    db: Session = Depends(get_db),
):
    return verify_certificate_token(db, token)
