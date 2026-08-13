from datetime import datetime

from pydantic import BaseModel, EmailStr


class UserSignUp(BaseModel):
    email: EmailStr
    password: str
    full_name: str | None = None

class UserSignIn(BaseModel):
    email: EmailStr
    password: str

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