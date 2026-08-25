from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class SignUpInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class LoginInput(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class UserOut(BaseModel):
    id: str
    email: Optional[str] = None


class AuthSession(BaseModel):
    access_token: str
    refresh_token: str
    expires_at: Optional[int] = None
    user: UserOut