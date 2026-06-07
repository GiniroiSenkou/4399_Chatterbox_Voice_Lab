from __future__ import annotations

SUPPORTED_MULTILINGUAL_LANGUAGES: dict[str, str] = {
    "ar": "Arabic",
    "da": "Danish",
    "de": "German",
    "el": "Greek",
    "en": "English",
    "es": "Spanish",
    "fi": "Finnish",
    "fr": "French",
    "he": "Hebrew",
    "hi": "Hindi",
    "it": "Italian",
    "ja": "Japanese",
    "ko": "Korean",
    "ms": "Malay",
    "nl": "Dutch",
    "no": "Norwegian",
    "pl": "Polish",
    "pt": "Portuguese",
    "ru": "Russian",
    "sv": "Swedish",
    "sw": "Swahili",
    "tr": "Turkish",
    "zh": "Chinese",
}


def is_supported_multilingual_language(language_id: str | None) -> bool:
    return bool(language_id and language_id.lower() in SUPPORTED_MULTILINGUAL_LANGUAGES)


def normalize_multilingual_language(language_id: str | None) -> str | None:
    if not language_id:
        return None
    normalized = language_id.strip().lower()
    return normalized if normalized in SUPPORTED_MULTILINGUAL_LANGUAGES else None
