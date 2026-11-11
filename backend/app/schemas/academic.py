from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

# As on the mother site, a quiz is passed at 80 % at least, PDF validation quizzes included.
QUIZ_PASS_PCT = 80.0


class ResourceCreate(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    resource_type: Literal["link", "pdf", "image", "video", "file"] = "link"
    url: str = Field(min_length=1, max_length=1024)
    course_day_id: int | None = None
    publish_now: bool = True

    @field_validator("title", "url")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class ResourceRead(BaseModel):
    id: int
    session_id: int
    course_day_id: int | None
    teacher_id: int | None
    teacher_name: str | None
    formation_title: str
    session_label: str
    title: str
    resource_type: str
    url: str
    published_at: datetime | None
    created_at: datetime


class QuizQuestionCreate(BaseModel):
    text: str = Field(min_length=2, max_length=2000)
    options: list[str] = Field(min_length=2, max_length=8)
    correct_index: int = Field(default=0, ge=0)
    # As on the mother site: one or several right answers, and points per question.
    selection_mode: Literal["single", "multiple"] = "single"
    correct_indices: list[int] | None = None
    points: float = Field(default=1.0, gt=0, le=100)

    @model_validator(mode="after")
    def validate_correct_index(self):
        if self.selection_mode == "multiple":
            indices = sorted(set(self.correct_indices or []))
            if not indices or any(index < 0 or index >= len(self.options) for index in indices):
                raise ValueError("Cochez au moins une bonne réponse parmi les options.")
            self.correct_indices = indices
            self.correct_index = indices[0]
        else:
            self.correct_indices = None
        if self.correct_index >= len(self.options):
            raise ValueError("La bonne réponse doit correspondre à une option.")
        return self


class QuizCreate(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    assessment_type: Literal["quiz", "exam"] = "quiz"
    duration_minutes: int | None = Field(default=None, ge=5, le=360)
    scheduled_at: datetime | None = None
    course_day_id: int | None = None
    pass_pct: float = Field(default=QUIZ_PASS_PCT, ge=QUIZ_PASS_PCT, le=100)
    questions: list[QuizQuestionCreate] = Field(min_length=1, max_length=100)


class QuizStatusUpdate(BaseModel):
    status: Literal["draft", "active", "closed"]


class TeacherQuizQuestionRead(BaseModel):
    id: int
    order_index: int
    text: str
    options: list[str]
    correct_index: int
    selection_mode: Literal["single", "multiple"] = "single"
    correct_indices: list[int] = Field(default_factory=list)
    points: float = 1.0


class TeacherQuizRead(BaseModel):
    id: int
    session_id: int
    course_day_id: int | None
    teacher_id: int | None
    teacher_name: str | None
    title: str
    assessment_type: str
    duration_minutes: int | None
    scheduled_at: datetime | None
    status: str
    pass_pct: float
    questions: list[TeacherQuizQuestionRead]
    attempts_count: int
    created_at: datetime


class StudentQuizQuestionRead(BaseModel):
    id: int
    order_index: int
    text: str
    options: list[str]
    selection_mode: Literal["single", "multiple"] = "single"
    points: float = 1.0


class QuizAttemptRead(BaseModel):
    id: int
    attempt_number: int
    score_pct: float
    submitted_at: datetime
    # The student's own correction, as on the mother site: one entry per question, -1 when unanswered.
    submitted_answers: list[list[int]] = Field(default_factory=list)
    correct_answers: list[list[int]] = Field(default_factory=list)


class StudentQuizRead(BaseModel):
    id: int
    session_id: int
    enrollment_id: int
    formation_title: str
    session_label: str
    teacher_name: str | None
    title: str
    assessment_type: str
    duration_minutes: int | None
    scheduled_at: datetime | None
    available_at: datetime | None = None
    is_locked: bool = False
    pass_pct: float
    questions: list[StudentQuizQuestionRead]
    attempts: list[QuizAttemptRead]
    best_score_pct: float | None
    passed: bool
    can_attempt: bool
    attempts_remaining: int
    next_attempt_available_at: datetime | None = None
    pdf_reading_pct: float | None = None
    pdf_reading_locked: bool = False


class QuizAttemptPayload(BaseModel):
    # One entry per question: an option index (-1 when unanswered) or, for multiple answers, a list.
    answers: list[int | list[int]] = Field(min_length=1)


class QuizResultAttemptRead(BaseModel):
    enrollment_id: int
    student_name: str
    attempt_number: int
    score_pct: float
    submitted_at: datetime


class TeacherQuizResultsRead(BaseModel):
    quiz_id: int
    title: str
    total_students: int
    attempts: list[QuizResultAttemptRead]


class LessonReaderRead(BaseModel):
    id: int
    title: str
    order_index: int
    lesson_type: str
    content: str | None
    video_url: str | None
    file_url: str | None
    quiz_id: int | None = None
    assignment_id: int | None = None
    resource_id: int | None = None
    available_at: datetime | None = None
    is_locked: bool = False
    completed: bool
    video_watched_pct: float = 0


class LessonVideoHeartbeatPayload(BaseModel):
    current_time_seconds: float = Field(ge=0, allow_inf_nan=False)
    duration_seconds: float = Field(gt=0, allow_inf_nan=False)
    playback_rate: float = Field(default=1.0, ge=0.25, le=3.0, allow_inf_nan=False)
    event: Literal["heartbeat", "seek", "ended"] = "heartbeat"


class ChapterReaderRead(BaseModel):
    id: int
    title: str
    order_index: int
    lessons: list[LessonReaderRead]


class CourseReaderRead(BaseModel):
    id: int
    title: str
    description: str
    teacher_name: str | None
    chapters: list[ChapterReaderRead]


class LearningSessionRead(BaseModel):
    enrollment_id: int
    session_id: int
    formation_id: int
    formation_title: str
    format_type: str
    dashboard_type: str
    session_label: str
    is_locked: bool
    available_at: datetime | None
    courses: list[CourseReaderRead]


class GradeRead(BaseModel):
    id: int
    session_id: int
    label: str
    source_type: str
    score: float
    max_score: float
    note: str
    created_at: datetime


class TeacherGradeEntry(BaseModel):
    enrollment_id: int
    course_day_id: int | None = None
    label: str = Field(min_length=1, max_length=180)
    score: float = Field(ge=0)
    max_score: float = Field(default=20, gt=0)
    note: str = Field(default="", max_length=2000)


class TeacherGradeRead(BaseModel):
    id: int
    enrollment_id: int
    student_name: str
    course_day_id: int | None
    course_day_title: str | None
    teacher_name: str | None
    is_own: bool
    source_type: str
    label: str
    score: float
    max_score: float
    note: str


class GradebookStudentRead(BaseModel):
    enrollment_id: int
    student_name: str


class GradebookCourseDayRead(BaseModel):
    id: int
    title: str
    scheduled_at: datetime
    can_grade: bool


class TeacherGradebookRead(BaseModel):
    session_id: int
    can_grade_session: bool
    students: list[GradebookStudentRead]
    course_days: list[GradebookCourseDayRead]
    grades: list[TeacherGradeRead]


# As on the mother site, a late student counts as present.
AttendanceStatus = Literal["present", "late", "absent", "excused"]


class AttendanceRowRead(BaseModel):
    enrollment_id: int
    student_id: int
    student_name: str
    status: AttendanceStatus | None
    # Live classes: what shows the student followed, for the teacher to check the prefilled attendance.
    live_minutes: int | None = None
    live_roll_calls_answered: int | None = None


class AttendanceMarkPayload(BaseModel):
    enrollment_id: int
    status: AttendanceStatus


class AttendanceCourseDayRead(BaseModel):
    course_day_id: int
    session_id: int
    title: str
    scheduled_at: datetime
    teacher_id: int | None
    teacher_name: str | None
    can_edit: bool
    edit_blocked_reason: str | None = None
    locks_at: datetime | None = None
    delivery_status: str | None
    report_submitted_at: datetime | None
    rows: list[AttendanceRowRead]
    live_roll_calls: int | None = None


class StudentAttendanceRead(BaseModel):
    course_day_id: int
    title: str
    scheduled_at: datetime
    status: AttendanceStatus | None


BadgeLevel = Literal["aventurier", "debutant", "intermediaire", "semi_pro", "professionnel"]


class BadgeRead(BaseModel):
    level: BadgeLevel
    label: str
    score_pct: float
    next_level: str | None
    lesson_progress_pct: float
    assignment_progress_pct: float | None
    quiz_progress_pct: float | None
    attendance_pct: float | None
    grade_average_pct: float | None
    final_project_validated: bool
    missing_requirements: list[str] = []
    ring_pct: float = 0.0


class ClassmateBadgeRead(BaseModel):
    """What a student may see of a classmate's badge: no score, grade or attendance."""

    level: BadgeLevel
    label: str
    ring_pct: float


class ProgressRead(BaseModel):
    enrollment_id: int
    session_id: int
    formation_title: str
    session_label: str
    completed_lessons: int
    total_lessons: int
    lesson_progress_pct: float
    submitted_assignments: int
    total_assignments: int
    attempted_quizzes: int
    total_quizzes: int
    attendance_present: int
    attendance_total: int
    grade_average_pct: float | None
    badge: BadgeRead


class ClassmateRead(BaseModel):
    user_id: int
    enrollment_id: int
    full_name: str
    avatar_url: str | None
    student_code: str | None
    is_current_user: bool
    badge: ClassmateBadgeRead


class StudentClassRead(BaseModel):
    session_id: int
    formation_title: str
    session_label: str
    classmates: list[ClassmateRead]


class DiscussionAuthorRead(BaseModel):
    user_id: int
    full_name: str
    avatar_url: str | None
    role: str
    is_current_user: bool


class DiscussionReplyRead(BaseModel):
    id: int
    author: DiscussionAuthorRead
    body: str
    image_url: str | None
    created_at: datetime


class DiscussionPostRead(BaseModel):
    id: int
    author: DiscussionAuthorRead
    body: str
    image_url: str | None
    created_at: datetime
    replies: list[DiscussionReplyRead]


class DiscussionCreate(BaseModel):
    body: str = Field(default="", max_length=2000)
    image_url: str | None = Field(default=None, max_length=1024)

    @model_validator(mode="after")
    def require_content(self):
        if not self.body.strip() and not self.image_url:
            raise ValueError("Ajoutez un message ou une image.")
        return self


class CertificateRead(BaseModel):
    enrollment_id: int
    certificate_number: str
    student_name: str
    formation_title: str
    issued_at: datetime
    status: str
    verification_token: str
    school_name: str | None = None
    logo_url: str | None = None
    primary_color: str | None = None
    secondary_color: str | None = None
    student_code: str | None = None
    session_label: str | None = None


class CertificateEligibilityRead(BaseModel):
    enrollment_id: int
    eligible: bool
    reason: str | None
    certificate: CertificateRead | None


class TeacherPerformanceSessionRead(BaseModel):
    session_id: int
    formation_title: str
    session_label: str
    enrolled_count: int
    progress_pct: float
    attendance_rate_pct: float | None
    quiz_average_score_pct: float | None
    pending_reviews_count: int


class TeacherPerformanceRead(BaseModel):
    total_sessions: int
    total_students: int
    attendance_rate_pct: float | None
    pending_reviews_count: int
    sessions: list[TeacherPerformanceSessionRead]



class SchoolPedagogyStudentRead(BaseModel):
    enrollment_id: int
    session_id: int
    student_id: int
    student_name: str
    student_code: str | None
    formation_title: str
    session_label: str
    enrollment_status: str
    progress_pct: float
    attendance_pct: float | None
    grade_average_pct: float | None
    submitted_assignments: int
    total_assignments: int
    attempted_quizzes: int
    total_quizzes: int
    alert_level: Literal["good", "warning", "danger"]
    alert_reasons: list[str]


class SchoolPedagogySessionRead(BaseModel):
    session_id: int
    formation_title: str
    session_label: str
    status: str
    enrolled_count: int
    seat_capacity: int
    fill_rate_pct: float
    progress_pct: float
    attendance_rate_pct: float | None
    pending_reviews_count: int
    at_risk_count: int


class SchoolTeacherPerformanceRead(BaseModel):
    teacher_id: int
    teacher_name: str
    teacher_code: str | None
    sessions_count: int
    students_count: int
    progress_pct: float
    attendance_rate_pct: float | None
    pending_reviews_count: int


class SchoolPedagogyOverviewRead(BaseModel):
    generated_at: datetime
    active_students: int
    active_sessions: int
    average_progress_pct: float
    average_attendance_pct: float | None
    at_risk_students: int
    pending_reviews_count: int
    students: list[SchoolPedagogyStudentRead]
    sessions: list[SchoolPedagogySessionRead]
    teachers: list[SchoolTeacherPerformanceRead]
