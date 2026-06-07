from __future__ import annotations

import re
import unicodedata
import uuid
from pathlib import Path

from app.config import settings


def generate_id() -> str:
    return str(uuid.uuid4())


def slugify_filename_component(value: str, fallback: str = "voice") -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    slug = re.sub(r"-{2,}", "-", slug)
    return slug or fallback


def voice_filename(name: str, voice_id: str) -> str:
    slug = slugify_filename_component(name)
    return f"{slug}-{voice_id[:8]}.wav"


def voice_path(voice_id: str, name: str) -> Path:
    return settings.voices_dir / voice_filename(name, voice_id)


def output_path(generation_id: str) -> Path:
    return settings.outputs_dir / f"{generation_id}.wav"


def temp_path(suffix: str = ".wav") -> Path:
    return settings.storage_root / "tmp" / f"{uuid.uuid4()}{suffix}"


def ensure_temp_dir() -> None:
    (settings.storage_root / "tmp").mkdir(parents=True, exist_ok=True)
