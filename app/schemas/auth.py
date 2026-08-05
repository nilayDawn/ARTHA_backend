from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class UserSignUp(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None

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
    full_name: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    created_at: datetime