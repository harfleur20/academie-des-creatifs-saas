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
    email: str = Field(min_length=3, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=8, max_length=72)


class GoogleAuthPayload(BaseModel):
    credential: str = Field(min_length=20, max_length=4096)


class PasswordResetRequestPayload(BaseModel):
    email: EmailStr
    school: str | None = Field(default=None, max_length=120)


class PasswordResetConfirmPayload(BaseModel):
    token: str = Field(min_length=20, max_length=4096)
    new_password: str = Field(min_length=8, max_length=72)


class MessageResponse(BaseModel):
    message: str


class AuthUser(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    full_name: str
    email: str
    phone: str | None = None
    avatar_url: str | None = None
    status: str
    platform_role: str
    created_at: datetime


class AuthResponse(BaseModel):
    message: str
    user: AuthUser
    access_token: str
    token_type: str = "Bearer"


class AuthSsoConfigRead(BaseModel):
    enabled: bool
    start_url: str | None = None


class AuthSsoExchangePayload(BaseModel):
    token: str = Field(min_length=20, max_length=512)


class ProfileUpdatePayload(BaseModel):
    full_name: str = Field(min_length=2, max_length=180)
    phone: str | None = Field(default=None, max_length=40)

    @field_validator("full_name")
    @classmethod
    def normalize_profile_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class PasswordChangePayload(BaseModel):
    current_password: str = Field(min_length=8, max_length=72)
    new_password: str = Field(min_length=8, max_length=72)
