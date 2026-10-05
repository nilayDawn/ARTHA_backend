from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class UserSignUp(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128, description="Password must be between 6 and 128 characters")
    full_name: str | None = Field(None, max_length=100, description="Full name of user")


class UserSignIn(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    email: str


class UserProfileResponse(BaseModel):
    id: str
    email: str
    full_name: str | None = None
    telegram_chat_id: str | None = None
    created_at: datetime


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=6, max_length=128)
