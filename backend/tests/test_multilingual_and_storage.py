from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.core.storage import slugify_filename_component, voice_filename
from app.schemas.generation import GenerationParams
from app.schemas.voice import VoiceCreate, VoiceUpdate
from app.services.generation_service import GenerationService
from app.services.text_chunker import chunk_text


def test_generation_params_accept_supported_language_and_normalize_case() -> None:
    params = GenerationParams(language_id="IT")
    assert params.language_id == "it"


def test_generation_params_reject_unsupported_language() -> None:
    with pytest.raises(ValidationError) as exc:
        GenerationParams(language_id="uk")

    assert "Unsupported language_id 'uk'" in str(exc.value)


def test_voice_schema_normalizes_language() -> None:
    voice = VoiceCreate(name="Narrator", language=" FR ")
    assert voice.language == "fr"


def test_voice_update_treats_blank_language_as_none() -> None:
    voice = VoiceUpdate(language="")
    assert voice.language is None


def test_generation_service_prefers_explicit_language() -> None:
    service = GenerationService(db=None, engine=None)  # type: ignore[arg-type]
    voice = SimpleNamespace(language="it")
    params = GenerationParams(language_id="fr")
    assert service._resolve_language_id("multilingual", params, voice) == "fr"


def test_generation_service_uses_saved_voice_language_when_request_missing() -> None:
    service = GenerationService(db=None, engine=None)  # type: ignore[arg-type]
    voice = SimpleNamespace(language="it")
    params = GenerationParams()
    assert service._resolve_language_id("multilingual", params, voice) == "it"


def test_generation_service_falls_back_to_english_when_no_language_available() -> None:
    service = GenerationService(db=None, engine=None)  # type: ignore[arg-type]
    voice = SimpleNamespace(language=None)
    params = GenerationParams()
    assert service._resolve_language_id("multilingual", params, voice) == "en"


def test_chunk_text_leaves_short_text_unchanged() -> None:
    text = "Ciao mondo."
    assert chunk_text(text, max_chars=300) == [text]


def test_chunk_text_splits_long_text_within_limit() -> None:
    sentence = "Questo e un test abbastanza lungo per verificare il chunking automatico."
    text = " ".join([sentence] * 10)
    chunks = chunk_text(text, max_chars=120)
    assert len(chunks) > 1
    assert all(len(chunk) <= 120 for chunk in chunks)


def test_slugify_filename_component_normalizes_unicode_and_punctuation() -> None:
    assert slugify_filename_component("Ren\u00e9e! Voce Italiana") == "renee-voce-italiana"


def test_voice_filename_uses_gui_name_and_short_id() -> None:
    assert voice_filename("My Saved Voice", "12345678-aaaa-bbbb-cccc-1234567890ab") == "my-saved-voice-12345678.wav"
