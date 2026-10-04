from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

AssignmentStudentStatus=Literal["pending","submitted","late","reviewed"]

class AssignmentCreate(BaseModel):
    title:str=Field(min_length=2,max_length=255)
    instructions:str=Field(default="",max_length=10000)
    due_date:datetime
    course_day_id:int|None=None
    is_final_project:bool=False

class AssignmentRead(BaseModel):
    id:int; session_id:int; course_day_id:int|None; teacher_id:int|None; teacher_name:str|None
    title:str; instructions:str; due_date:datetime; is_final_project:bool
    submissions_count:int; created_at:datetime

class StudentAssignmentRead(BaseModel):
    id:int; enrollment_id:int; session_id:int; session_label:str; formation_title:str; teacher_name:str|None
    title:str; instructions:str; due_date:datetime; is_final_project:bool
    is_locked:bool=False; available_at:datetime|None=None
    student_status:AssignmentStudentStatus; submitted_at:datetime|None; file_url:str|None
    is_reviewed:bool; review_score:float|None; review_max_score:float; comment_count:int

class AssignmentSubmit(BaseModel):
    file_url:str=Field(min_length=1,max_length=1024)

class SubmissionRead(BaseModel):
    id:int; enrollment_id:int; student_name:str; file_url:str; submitted_at:datetime
    is_reviewed:bool; review_score:float|None; review_max_score:float; comment_count:int

class ReviewSubmission(BaseModel):
    review_score:float=Field(ge=0,le=20)

class CommentCreate(BaseModel):
    body:str=Field(default="",max_length=4000)
    attachment_url:str|None=Field(default=None,max_length=1024)

class CommentRead(BaseModel):
    id:int; assignment_id:int; enrollment_id:int; author_role:Literal["student","teacher"]
    author_name:str; body:str; attachment_url:str|None; created_at:datetime
