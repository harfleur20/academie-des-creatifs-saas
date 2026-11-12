import re
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator

AssignmentStudentStatus=Literal["pending","submitted","late","reviewed"]

def _clean_brief_text(value:str)->str:
    """Remove raw HTML while keeping the line breaks of the teacher's text."""
    text=str(value).replace("\r\n","\n").replace("\r","\n")
    text=re.sub(r"<br\s*/?>","\n",text,flags=re.IGNORECASE)
    text=re.sub(r"<[^>]+>","",text)
    text=re.sub(r"[ \t]+"," ",text)
    text=re.sub(r" *\n *","\n",text)
    text=re.sub(r"\n{3,}","\n\n",text)
    return text.strip()

class AssignmentRubricItem(BaseModel):
    label:str=Field(min_length=1,max_length=100)
    points:float=Field(gt=0,le=20)
    description:str=Field(min_length=1,max_length=320)

    @field_validator("label","description")
    @classmethod
    def clean_text(cls,value:str)->str:
        cleaned=_clean_brief_text(value)
        if not cleaned: raise ValueError("Texte requis.")
        return cleaned

class AssignmentBrief(BaseModel):
    context:str=Field(default="",max_length=800)
    objective:str=Field(min_length=1,max_length=600)
    deliverables:list[str]=Field(min_length=1,max_length=8)
    steps:list[str]=Field(min_length=1,max_length=8)
    evaluation_criteria:list[AssignmentRubricItem]=Field(min_length=1,max_length=8)
    submission_method:str=Field(min_length=1,max_length=400)
    tips:list[str]=Field(default_factory=list,max_length=6)

    @field_validator("context","objective","submission_method")
    @classmethod
    def clean_scalar_text(cls,value:str)->str:
        return _clean_brief_text(value)

    @field_validator("deliverables","steps","tips")
    @classmethod
    def clean_list_text(cls,values:list[str])->list[str]:
        cleaned:list[str]=[]; seen:set[str]=set()
        for value in values:
            item=_clean_brief_text(value)
            if item and item.casefold() not in seen:
                cleaned.append(item); seen.add(item.casefold())
        return cleaned

    @model_validator(mode="after")
    def validate_structure(self)->"AssignmentBrief":
        if not self.objective: raise ValueError("L'objectif du devoir est requis.")
        if not self.deliverables: raise ValueError("Ajoutez au moins un livrable.")
        if not self.steps: raise ValueError("Ajoutez au moins une étape.")
        if not self.submission_method: raise ValueError("La modalité de rendu est requise.")
        if abs(round(sum(item.points for item in self.evaluation_criteria),2)-20.0)>0.01:
            raise ValueError("Le barème d'évaluation doit totaliser exactement 20 points.")
        return self

class AssignmentCreate(BaseModel):
    title:str=Field(min_length=2,max_length=255)
    instructions:str=Field(default="",max_length=10000)
    brief:AssignmentBrief|None=None
    due_date:datetime
    course_day_id:int|None=None
    is_final_project:bool=False

class AssignmentUpdate(BaseModel):
    title:str|None=Field(default=None,min_length=2,max_length=255)
    instructions:str|None=Field(default=None,max_length=10000)
    brief:AssignmentBrief|None=None
    due_date:datetime|None=None
    course_day_id:int|None=None
    is_final_project:bool|None=None

class AssignmentRead(BaseModel):
    id:int; session_id:int; course_day_id:int|None; teacher_id:int|None; teacher_name:str|None
    title:str; publication_status:Literal["draft","published"]; instructions:str; brief:AssignmentBrief|None; due_date:datetime; is_final_project:bool
    submissions_count:int; created_at:datetime
    can_manage:bool; delete_blocked_reason:str|None

class StudentAssignmentRead(BaseModel):
    id:int; enrollment_id:int; session_id:int; session_label:str; formation_title:str; teacher_name:str|None
    title:str; instructions:str; brief:AssignmentBrief|None; due_date:datetime; is_final_project:bool
    is_locked:bool=False; available_at:datetime|None=None
    student_status:AssignmentStudentStatus; submitted_at:datetime|None; file_url:str|None
    is_reviewed:bool; review_score:float|None; review_max_score:float; comment_count:int
    # Live and presentiel: the session is over, nothing more can be handed in.
    submissions_closed:bool=False

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
