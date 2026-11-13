from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TextRequest(BaseModel):
    text: str = Field(min_length=8, max_length=12000)
    language: Literal["en", "hi", "mr", "auto"] = "auto"
    kind: Literal["text", "image"] = "text"
    ocr_confidence: float | None = Field(default=None, ge=0, le=1)
    source_filename: str | None = Field(default=None, max_length=255)
    source_content_type: str | None = Field(default=None, max_length=100)
    source_sha256: str | None = Field(default=None, pattern=r"^[a-fA-F0-9]{64}$")
    source_bytes: int | None = Field(default=None, ge=0, le=8_000_000)

    @field_validator("text")
    @classmethod
    def non_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Text cannot be blank.")
        return value.strip()


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=10, max_length=128)

    @field_validator("full_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Name is required.")
        return value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        local, separator, domain = value.partition("@")
        if not separator or not local or "@" in domain or "." not in domain or domain.startswith(".") or domain.endswith(".") or " " in value:
            raise ValueError("Enter a valid email address.")
        return value


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.strip().lower()


class ProfileUpdate(BaseModel):
    full_name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=5, max_length=254)

    @field_validator("full_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Name is required.")
        return value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return RegisterRequest.normalize_email(value)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=10, max_length=128)


class PasswordResetRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return RegisterRequest.normalize_email(value)


class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=32, max_length=128)
    new_password: str = Field(min_length=10, max_length=128)


class AccountDeleteRequest(BaseModel):
    password: str = Field(min_length=1, max_length=128)


class ContactRequest(BaseModel):
    full_name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=5, max_length=254)
    message: str = Field(min_length=10, max_length=4000)

    @field_validator("full_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if not value:
            raise ValueError("Name is required.")
        return value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return RegisterRequest.normalize_email(value)

    @field_validator("message")
    @classmethod
    def clean_message(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 10:
            raise ValueError("Please provide at least 10 characters.")
        return value


class UserResponse(BaseModel):
    id: int
    full_name: str
    email: str


class FactCheck(BaseModel):
    publisher: str
    title: str
    url: str
    rating: str | None = None
    review_date: str | None = None


class AnalysisResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: str
    status: str = "completed"
    label: str
    verdict: str | None = None
    risk_score: float | None = None
    model_confidence: float | None = None
    language: str | None = None
    model_status: str
    model_name: str | None = None
    summary: str
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    fact_checks: list[FactCheck] = Field(default_factory=list)
    fact_check_status: str = "not_configured"
    processing_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None


class OCRResult(BaseModel):
    text: str
    language: str | None = None
    status: str
    confidence: float | None = None
