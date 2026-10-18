from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class _Credentials(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("password")
    @classmethod
    def fits_bcrypt_limit(cls, value: str) -> str:
        # bcrypt only uses the first 72 bytes of a password, so longer ones are rejected
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 bytes long")
        return value


class RegisterRequest(_Credentials):
    password: str = Field(min_length=8, max_length=72)


class LoginRequest(_Credentials):
    password: str = Field(min_length=1, max_length=72)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    created_at: datetime
