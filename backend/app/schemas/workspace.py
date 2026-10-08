from datetime import date

from pydantic import BaseModel


class TeacherSessionWorkspaceRead(BaseModel):
    formation_id: int
    formation_title: str
    formation_image: str | None
    format_type: str
    session_id: int
    session_label: str
    start_date: date
    end_date: date
    campus_label: str | None
    seat_capacity: int
    status: str
    assignment_role: str
    student_count: int
    course_count: int


class TeacherWorkspaceRead(BaseModel):
    teacher_code: str
    sessions: list[TeacherSessionWorkspaceRead]
    total_sessions: int
    total_students: int
    total_courses: int


class StudentSessionWorkspaceRead(BaseModel):
    enrollment_id: int
    formation_id: int
    formation_title: str
    formation_image: str | None
    format_type: str
    dashboard_type: str
    session_id: int
    session_label: str
    start_date: date
    end_date: date
    teacher_name: str | None
    campus_label: str | None
    session_status: str
    enrollment_status: str
    course_count: int


class StudentWorkspaceRead(BaseModel):
    student_code: str | None
    sessions: list[StudentSessionWorkspaceRead]
    total_sessions: int
    total_courses: int
