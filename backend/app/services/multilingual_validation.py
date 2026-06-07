from __future__ import annotations

import re

from app.core.languages import SUPPORTED_MULTILINGUAL_LANGUAGES

MIN_MEANINGFUL_MULTILINGUAL_CHARS = 24
MIN_MEANINGFUL_MULTILINGUAL_TOKENS = 5
_TAG_PATTERN = re.compile(r"\[\s*[^\]]+\s*\]")
_NON_ALNUM_PATTERN = re.compile(r"[^\w\s]", re.UNICODE)
_TOKEN_PATTERN = re.compile(r"\b\w+\b", re.UNICODE)

MULTILINGUAL_SHORT_TEXT_ERROR = (
    "Multilingual generation needs a longer prompt to avoid artifact audio. "
    "Use at least a short full sentence with about 5 meaningful words or 24 letters/numbers. "
    "Italian works best with an Italian reference clip. If you are cloning across languages, lower CFG Weight toward 0.0-0.3."
)


def strip_multilingual_noise(text: str) -> str:
    stripped_tags = _TAG_PATTERN.sub(" ", text)
    stripped_symbols = _NON_ALNUM_PATTERN.sub(" ", stripped_tags)
    return re.sub(r"\s+", " ", stripped_symbols).strip()


def analyze_multilingual_prompt(text: str) -> dict[str, int | str]:
    cleaned = strip_multilingual_noise(text)
    meaningful_tokens = _TOKEN_PATTERN.findall(cleaned)
    meaningful_characters = sum(1 for ch in cleaned if ch.isalnum())
    return {
        "cleaned_text": cleaned,
        "meaningful_characters": meaningful_characters,
        "meaningful_tokens": len(meaningful_tokens),
    }


def is_multilingual_prompt_too_short(text: str) -> bool:
    analysis = analyze_multilingual_prompt(text)
    return (
        analysis["meaningful_characters"] < MIN_MEANINGFUL_MULTILINGUAL_CHARS
        or analysis["meaningful_tokens"] < MIN_MEANINGFUL_MULTILINGUAL_TOKENS
    )


def supported_multilingual_language_labels() -> str:
    return ", ".join(f"{label} ({lang_id})" for lang_id, label in sorted(SUPPORTED_MULTILINGUAL_LANGUAGES.items()))
