from pydantic import BaseModel


class OnboardingStepRead(BaseModel):
    key: str
    label: str
    description: str
    completed: bool
    available: bool = True
    path: str


class OnboardingStatusRead(BaseModel):
    completed_steps: int
    total_steps: int
    progress_percent: int
    is_complete: bool
    next_step: OnboardingStepRead | None
    steps: list[OnboardingStepRead]
