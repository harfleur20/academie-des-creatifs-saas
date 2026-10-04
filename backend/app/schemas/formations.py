from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


FORMATION_STATUSES = "^(draft|published|archived)$"
FORMATION_FORMATS = "^(live|ligne|presentiel)$"
SESSION_STATUSES = "^(planned|open|completed|cancelled)$"
TEACHER_ROLES = "^(principal|intervenant)$"
ENROLLMENT_STATUSES = "^(active|completed|cancelled)$"
COURSE_STATUSES = "^(draft|published|archived)$"
LESSON_TYPES = "^(text|video|pdf|quiz|assignment|resource)$"


class FormationCreate(BaseModel):
    slug: str = Field(
        min_length=2,
        max_length=255,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    title: str = Field(min_length=2, max_length=255)
    description: str = Field(default="", max_length=5000)
    category: str = Field(default="", max_length=120)
    level: str = Field(default="", max_length=120)
    format_type: str = Field(default="ligne", pattern=FORMATION_FORMATS)
    training_hours: int | None = Field(default=None, ge=1, le=10000)
    short_description: str = Field(default="", max_length=500)
    cover_image_url: str | None = Field(default=None, max_length=1024)
    objectives: str = Field(default="", max_length=10000)
    prerequisites: str = Field(default="", max_length=10000)
    public_program: str = Field(default="", max_length=30000)
    price_cents: int = Field(default=0, ge=0, le=2_000_000_000)
    currency: str = Field(default="XAF", min_length=3, max_length=3)
    allow_installments: bool = False
    installment_count: int = Field(default=3, ge=2, le=12)
    is_featured: bool = False
    featured_order: int = Field(default=0, ge=0, le=1000)
    status: str = Field(default="draft", pattern=FORMATION_STATUSES)


class FormationUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    category: str | None = Field(default=None, max_length=120)
    level: str | None = Field(default=None, max_length=120)
    format_type: str | None = Field(default=None, pattern=FORMATION_FORMATS)
    training_hours: int | None = Field(default=None, ge=1, le=10000)
    short_description: str | None = Field(default=None, max_length=500)
    cover_image_url: str | None = Field(default=None, max_length=1024)
    objectives: str | None = Field(default=None, max_length=10000)
    prerequisites: str | None = Field(default=None, max_length=10000)
    public_program: str | None = Field(default=None, max_length=30000)
    price_cents: int | None = Field(default=None, ge=0, le=2_000_000_000)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    allow_installments: bool | None = None
    installment_count: int | None = Field(default=None, ge=2, le=12)
    is_featured: bool | None = None
    featured_order: int | None = Field(default=None, ge=0, le=1000)
    status: str | None = Field(default=None, pattern=FORMATION_STATUSES)


class FormationSummaryRead(BaseModel):
    id: int
    organization_id: int
    slug: str
    title: str
    description: str
    category: str
    level: str
    format_type: str
    training_hours: int | None
    short_description: str
    cover_image_url: str | None
    objectives: str
    prerequisites: str
    public_program: str
    price_cents: int
    currency: str
    allow_installments: bool
    installment_count: int
    is_featured: bool
    featured_order: int
    status: str
    session_count: int
    teacher_count: int
    student_count: int
    course_count: int
    created_at: datetime


class SessionCreate(BaseModel):
    label: str = Field(min_length=2, max_length=180)
    start_date: date
    end_date: date
    campus_label: str | None = Field(default=None, max_length=180)
    seat_capacity: int = Field(default=0, ge=0, le=100000)
    enrollment_open_at: datetime | None = None
    enrollment_close_at: datetime | None = None
    price_override_cents: int | None = Field(default=None, ge=0, le=2_000_000_000)
    status: str = Field(default="planned", pattern=SESSION_STATUSES)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("La date de fin doit être postérieure ou égale à la date de début.")
        if (
            self.enrollment_open_at is not None
            and self.enrollment_close_at is not None
            and self.enrollment_close_at < self.enrollment_open_at
        ):
            raise ValueError("La clôture des inscriptions doit suivre leur ouverture.")
        return self


class SessionUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=2, max_length=180)
    start_date: date | None = None
    end_date: date | None = None
    campus_label: str | None = Field(default=None, max_length=180)
    seat_capacity: int | None = Field(default=None, ge=0, le=100000)
    enrollment_open_at: datetime | None = None
    enrollment_close_at: datetime | None = None
    price_override_cents: int | None = Field(default=None, ge=0, le=2_000_000_000)
    status: str | None = Field(default=None, pattern=SESSION_STATUSES)


class TeacherAssignmentCreate(BaseModel):
    user_id: int = Field(gt=0)
    role: str = Field(default="intervenant", pattern=TEACHER_ROLES)


class EnrollmentCreate(BaseModel):
    user_id: int = Field(gt=0)


class EnrollmentUpdate(BaseModel):
    status: str = Field(pattern=ENROLLMENT_STATUSES)


class CourseCreate(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    description: str = Field(default="", max_length=5000)
    teacher_id: int | None = Field(default=None, gt=0)
    status: str = Field(default="draft", pattern=COURSE_STATUSES)


class CourseUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    teacher_id: int | None = Field(default=None, gt=0)
    status: str | None = Field(default=None, pattern=COURSE_STATUSES)


class ChapterCreate(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    order_index: int = Field(default=0, ge=0, le=10000)


class LessonCreate(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    order_index: int = Field(default=0, ge=0, le=10000)
    lesson_type: str = Field(default="text", pattern=LESSON_TYPES)
    content: str | None = Field(default=None, max_length=100000)
    video_url: str | None = Field(default=None, max_length=512)
    file_url: str | None = Field(default=None, max_length=512)
    quiz_id: int | None = Field(default=None, gt=0)
    assignment_id: int | None = Field(default=None, gt=0)
    resource_id: int | None = Field(default=None, gt=0)
    available_at: datetime | None = None


class TeacherAssignmentRead(BaseModel):
    id: int
    teacher_id: int
    teacher_name: str
    teacher_email: str
    role: str
    assigned_at: datetime


class EnrollmentRead(BaseModel):
    id: int
    student_id: int
    student_name: str
    student_email: str
    status: str
    created_at: datetime


class LessonRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    order_index: int
    lesson_type: str
    publication_status: str
    content: str | None
    video_url: str | None
    file_url: str | None
    quiz_id: int | None
    assignment_id: int | None
    resource_id: int | None
    available_at: datetime | None


class ChapterRead(BaseModel):
    id: int
    title: str
    order_index: int
    lessons: list[LessonRead]


class CourseRead(BaseModel):
    id: int
    title: str
    description: str
    teacher_id: int | None
    teacher_name: str | None
    status: str
    chapters: list[ChapterRead]
    created_at: datetime


class SessionRead(BaseModel):
    id: int
    label: str
    start_date: date
    end_date: date
    campus_label: str | None
    seat_capacity: int
    enrollment_open_at: datetime | None
    enrollment_close_at: datetime | None
    price_override_cents: int | None
    status: str
    teachers: list[TeacherAssignmentRead]
    enrollments: list[EnrollmentRead]
    courses: list[CourseRead]
    created_at: datetime


class FormationDetailRead(FormationSummaryRead):
    sessions: list[SessionRead]
