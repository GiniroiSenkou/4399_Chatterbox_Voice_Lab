from __future__ import annotations

import pytest

from app.core.exceptions import InvalidGenerationRequestError
from app.schemas.generation import GenerationParams
from app.services.generation_service import GenerationService
from app.services.multilingual_validation import (
    MULTILINGUAL_SHORT_TEXT_ERROR,
    analyze_multilingual_prompt,
    is_multilingual_prompt_too_short,
)


def test_multilingual_prompt_rejects_short_text() -> None:
    assert is_multilingual_prompt_too_short("Va bene.")


def test_multilingual_prompt_accepts_meaningful_italian_sentence() -> None:
    assert not is_multilingual_prompt_too_short("Ciao, come stai oggi? Ti richiamo tra qualche minuto.")


def test_multilingual_prompt_ignores_punctuation_and_tags() -> None:
    analysis = analyze_multilingual_prompt("... [laugh] !! ? va bene")
    assert analysis["meaningful_tokens"] == 2
    assert analysis["meaningful_characters"] == 7


def test_generation_service_blocks_short_multilingual_request() -> None:
    service = GenerationService(db=None, engine=None)  # type: ignore[arg-type]
    with pytest.raises(InvalidGenerationRequestError) as exc:
        service._validate_multilingual_request("Va bene.", "multilingual")

    assert MULTILINGUAL_SHORT_TEXT_ERROR in str(exc.value.detail)


def test_generation_service_does_not_block_non_multilingual_short_text() -> None:
    service = GenerationService(db=None, engine=None)  # type: ignore[arg-type]
    assert service._validate_multilingual_request("Ok.", "turbo") is None


def test_generation_service_accepts_longer_multilingual_prompt() -> None:
    service = GenerationService(db=None, engine=None)  # type: ignore[arg-type]
    analysis = service._validate_multilingual_request(
        "Ciao, come stai oggi? Ti richiamo appena finisco questa chiamata.",
        "multilingual",
    )
    assert analysis is not None
    assert analysis["meaningful_tokens"] >= 5


def test_generation_params_language_normalization_still_works() -> None:
    params = GenerationParams(language_id="IT")
    assert params.language_id == "it"
