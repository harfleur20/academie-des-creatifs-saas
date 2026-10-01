from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegisterPayload(BaseModel):
    full_name: str = Field(min_length=2, max_length=180)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)

    @field_validator("full_name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return value.strip()


class LoginPayload(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)


class AuthUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str
    status: str
    platform_role: str
    created_at: datetime


class AuthResponse(BaseModel):
    message: str
    user: AuthUser
    access_token: str
    token_type: str = "Bearer"
