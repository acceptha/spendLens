from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"  # noqa: S105


class RefreshResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"  # noqa: S105


class SignupRequest(BaseModel):
    email: EmailStr
    # 길이/문자 정책은 validate_password_policy가 단일 소스. max_length는 argon2 DOS 가드.
    password: str = Field(max_length=128)


class SignupResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"  # noqa: S105
