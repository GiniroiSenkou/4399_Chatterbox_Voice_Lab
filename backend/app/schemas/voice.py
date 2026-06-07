from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.core.languages import SUPPORTED_MULTILINGUAL_LANGUAGES, normalize_multilingual_language


class VoiceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    tags: list[str] | None = None
    language: str | None = None

    @field_validator("language")
    @classmethod
    def validate_language(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not value.strip():
            return None
        normalized = normalize_multilingual_language(value)
        if normalized:
            return normalized
        supported = ", ".join(sorted(SUPPORTED_MULTILINGUAL_LANGUAGES))
        raise ValueError(f"Unsupported language '{value}'. Supported values: {supported}")


class VoiceUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    tags: list[str] | None = None
    language: str | None = None

    @field_validator("language")
    @classmethod
    def validate_language(cls, value: str | None) -> str | None:
        return VoiceCreate.validate_language(value)


class VoiceResponse(BaseModel):
    id: str
    name: str
    description: str | None
    tags: list[str] | None
    original_filename: str | None
    file_format: str
    sample_rate: int
    duration_ms: int
    language: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class VoiceListResponse(BaseModel):
    voices: list[VoiceResponse]
    total: int
