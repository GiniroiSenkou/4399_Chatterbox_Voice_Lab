from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import torch
import torchaudio
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.languages import normalize_multilingual_language, resolve_multilingual_language_hint
from app.core.events import event_bus
from app.core.exceptions import GenerationNotFoundError, VoiceNotFoundError, InvalidGenerationRequestError
from app.core.storage import generate_id, output_path
from app.models.generation import Generation
from app.models.voice_profile import VoiceProfile
from app.schemas.generation import GenerateRequest, GenerateABRequest, GenerationParams
from app.services.engine_manager import EngineManager
from app.services.multilingual_validation import (
    MULTILINGUAL_SHORT_TEXT_ERROR,
    analyze_multilingual_prompt,
    is_multilingual_prompt_too_short,
)
from app.services.text_chunker import chunk_text
from app.utils.paralinguistic import prepare_text_for_model

logger = logging.getLogger(__name__)
MULTILINGUAL_CHUNK_MAX_CHARS = 300


class GenerationService:
    def __init__(self, db: AsyncSession, engine: EngineManager) -> None:
        self.db = db
        self.engine = engine

    async def _get_voice(self, voice_id: str) -> VoiceProfile:
        result = await self.db.execute(
            select(VoiceProfile).where(VoiceProfile.id == voice_id)
        )
        voice = result.scalar_one_or_none()
        if not voice:
            raise VoiceNotFoundError(voice_id)
        return voice

    def _resolve_voice_tag_language(self, voice: VoiceProfile) -> str | None:
        if not voice.tags:
            return None
        try:
            tags = json.loads(voice.tags)
        except json.JSONDecodeError:
            logger.warning("Failed to parse voice tags for language resolution", extra={"voice_id": voice.id})
            return None
        if not isinstance(tags, list):
            return None
        for tag in tags:
            if not isinstance(tag, str):
                continue
            resolved = resolve_multilingual_language_hint(tag)
            if resolved:
                return resolved
        return None

    def _resolve_language_id(self, model: str, params: GenerationParams, voice: VoiceProfile) -> str | None:
        if model != "multilingual":
            return None

        requested = normalize_multilingual_language(params.language_id)
        if requested:
            return requested

        saved_voice_language = resolve_multilingual_language_hint(voice.language)
        if saved_voice_language:
            return saved_voice_language

        tagged_voice_language = self._resolve_voice_tag_language(voice)
        if tagged_voice_language:
            return tagged_voice_language

        return "en"

    def _validate_multilingual_request(self, text: str, model: str) -> dict[str, int | str] | None:
        if model != "multilingual":
            return None

        analysis = analyze_multilingual_prompt(text)
        if is_multilingual_prompt_too_short(text):
            raise InvalidGenerationRequestError(MULTILINGUAL_SHORT_TEXT_ERROR)

        return analysis

    def _build_engine_params(
        self,
        model: str,
        params: GenerationParams,
        voice: VoiceProfile,
    ) -> dict[str, object]:
        param_dict: dict[str, object] = params.model_dump(exclude_none=True)
        param_dict.pop("norm_loudness", None)

        resolved_language = self._resolve_language_id(model, params, voice)
        if resolved_language:
            param_dict["language_id"] = resolved_language
        else:
            param_dict.pop("language_id", None)

        return param_dict

    async def _generate_audio(
        self,
        gen_id: str,
        text: str,
        voice: VoiceProfile,
        model: str,
        params: GenerationParams,
    ) -> tuple[Path, int]:
        param_dict = self._build_engine_params(model, params, voice)
        prepared_text = prepare_text_for_model(text, model)

        if model != "multilingual":
            return await self.engine.generate(
                model_type=model,
                text=prepared_text,
                voice_path=Path(voice.file_path),
                generation_id=gen_id,
                **param_dict,
            )

        chunks = chunk_text(text, max_chars=MULTILINGUAL_CHUNK_MAX_CHARS)
        prepared_chunks = [prepare_text_for_model(chunk, model) for chunk in chunks]
        if len(prepared_chunks) <= 1:
            return await self.engine.generate(
                model_type=model,
                text=prepared_text,
                voice_path=Path(voice.file_path),
                generation_id=gen_id,
                **param_dict,
            )

        wav_chunks: list[torch.Tensor] = []
        sample_rate: int | None = None
        total_chunks = len(prepared_chunks)

        for idx, chunk in enumerate(prepared_chunks, start=1):
            await event_bus.publish("generation:progress", {
                "job_id": gen_id,
                "progress": 0.2 + (0.55 * idx / total_chunks),
                "stage": f"generating chunk {idx}/{total_chunks}",
            })

            wav, current_sample_rate = await self.engine.synthesize(
                model_type=model,
                text=chunk,
                voice_path=Path(voice.file_path),
                **param_dict,
            )
            if sample_rate is None:
                sample_rate = current_sample_rate
            elif sample_rate != current_sample_rate:
                raise ValueError("Chunked multilingual generation produced mismatched sample rates")
            wav_chunks.append(wav)

        stitched_wav = torch.cat(wav_chunks, dim=-1)
        assert sample_rate is not None

        await event_bus.publish("generation:progress", {
            "job_id": gen_id,
            "progress": 0.85,
            "stage": "saving",
        })

        out_path = output_path(gen_id)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(torchaudio.save, str(out_path), stitched_wav, sample_rate)
        duration_ms = int(stitched_wav.shape[-1] / sample_rate * 1000)
        return out_path, duration_ms

    async def generate(self, request: GenerateRequest) -> str:
        """Submit a generation job. Returns job_id."""
        voice = await self._get_voice(request.voice_id)
        multilingual_prompt_meta = self._validate_multilingual_request(request.text, request.model)
        params_payload = request.params.model_dump()
        if request.preset_name:
            params_payload["_preset_name"] = request.preset_name
        params_payload["_voice_name"] = voice.name
        if voice.language:
            params_payload["_voice_language"] = voice.language
        resolved_language = self._resolve_language_id(request.model, request.params, voice)
        if resolved_language:
            params_payload["_resolved_language_id"] = resolved_language
        if multilingual_prompt_meta:
            params_payload["_multilingual_prompt_meta"] = multilingual_prompt_meta

        gen_id = generate_id()
        generation = Generation(
            id=gen_id,
            voice_id=request.voice_id,
            text=request.text,
            model=request.model,
            params=json.dumps(params_payload),
            status="queued",
        )
        self.db.add(generation)
        await self.db.flush()

        await event_bus.publish("generation:queued", {"job_id": gen_id})

        # Launch generation in background
        asyncio.create_task(
            self._run_generation(gen_id, request.text, voice, request.model, request.params)
        )

        return gen_id

    async def generate_ab(self, request: GenerateABRequest) -> tuple[str, str, str]:
        """Submit A/B comparison. Returns (job_id_a, job_id_b, ab_pair_id)."""
        voice = await self._get_voice(request.voice_id)
        multilingual_prompt_meta = self._validate_multilingual_request(request.text, request.model_b)
        params_payload = request.params.model_dump()
        if request.preset_name:
            params_payload["_preset_name"] = request.preset_name
        params_payload["_voice_name"] = voice.name
        if voice.language:
            params_payload["_voice_language"] = voice.language
        resolved_language = (
            self._resolve_language_id(request.model_a, request.params, voice)
            or self._resolve_language_id(request.model_b, request.params, voice)
        )
        if resolved_language:
            params_payload["_resolved_language_id"] = resolved_language
        if multilingual_prompt_meta:
            params_payload["_multilingual_prompt_meta"] = multilingual_prompt_meta
        ab_pair_id = generate_id()

        gen_id_a = generate_id()
        gen_a = Generation(
            id=gen_id_a,
            voice_id=request.voice_id,
            text=request.text,
            model=request.model_a,
            params=json.dumps(params_payload),
            status="queued",
            ab_pair_id=ab_pair_id,
        )

        gen_id_b = generate_id()
        gen_b = Generation(
            id=gen_id_b,
            voice_id=request.voice_id,
            text=request.text,
            model=request.model_b,
            params=json.dumps(params_payload),
            status="queued",
            ab_pair_id=ab_pair_id,
        )

        self.db.add(gen_a)
        self.db.add(gen_b)
        await self.db.flush()

        # Launch both sequentially (share model lock)
        asyncio.create_task(
            self._run_ab_generations(
                gen_id_a, gen_id_b,
                request.text, voice,
                request.model_a, request.model_b,
                request.params,
            )
        )

        return gen_id_a, gen_id_b, ab_pair_id

    async def _run_generation(
        self, gen_id: str, text: str, voice: VoiceProfile, model: str, params: GenerationParams
    ) -> None:
        """Background task to run TTS generation."""
        try:
            await event_bus.publish("generation:started", {
                "job_id": gen_id,
                "model": model,
            })

            # Update status
            await self._update_status(gen_id, "processing")
            out_path, duration_ms = await self._generate_audio(gen_id, text, voice, model, params)

            # Update DB
            await self._complete_generation(gen_id, str(out_path), duration_ms)

            await event_bus.publish("generation:complete", {
                "job_id": gen_id,
                "generation_id": gen_id,
                "output_url": f"/api/v1/generate/{gen_id}/audio",
                "duration_ms": duration_ms,
            })

        except Exception as e:
            logger.exception(f"Generation {gen_id} failed")
            await self._fail_generation(gen_id, str(e))
            await event_bus.publish("generation:failed", {
                "job_id": gen_id,
                "error": str(e),
            })

    async def _run_ab_generations(
        self,
        gen_id_a: str,
        gen_id_b: str,
        text: str,
        voice: VoiceProfile,
        model_a: str,
        model_b: str,
        params: GenerationParams,
    ) -> None:
        """Run A/B comparison generations sequentially."""
        for gen_id, model in [(gen_id_a, model_a), (gen_id_b, model_b)]:
            try:
                await event_bus.publish("generation:started", {"job_id": gen_id, "model": model})
                await self._update_status(gen_id, "processing")
                out_path, duration_ms = await self._generate_audio(gen_id, text, voice, model, params)

                await self._complete_generation(gen_id, str(out_path), duration_ms)
                await event_bus.publish("generation:complete", {
                    "job_id": gen_id,
                    "generation_id": gen_id,
                    "output_url": f"/api/v1/generate/{gen_id}/audio",
                    "duration_ms": duration_ms,
                })
            except Exception as e:
                logger.exception(f"A/B generation {gen_id} failed")
                await self._fail_generation(gen_id, str(e))
                await event_bus.publish("generation:failed", {"job_id": gen_id, "error": str(e)})

    async def _update_status(self, gen_id: str, status: str) -> None:
        from app.core.database import async_session
        async with async_session() as session:
            result = await session.execute(
                select(Generation).where(Generation.id == gen_id)
            )
            gen = result.scalar_one_or_none()
            if gen:
                gen.status = status
                await session.commit()

    async def _complete_generation(self, gen_id: str, output_path: str, duration_ms: int) -> None:
        from app.core.database import async_session
        async with async_session() as session:
            result = await session.execute(
                select(Generation).where(Generation.id == gen_id)
            )
            gen = result.scalar_one_or_none()
            if gen:
                gen.status = "completed"
                gen.output_path = output_path
                gen.duration_ms = duration_ms
                await session.commit()

    async def _fail_generation(self, gen_id: str, error: str) -> None:
        from app.core.database import async_session
        async with async_session() as session:
            result = await session.execute(
                select(Generation).where(Generation.id == gen_id)
            )
            gen = result.scalar_one_or_none()
            if gen:
                gen.status = "failed"
                gen.error_message = error
                await session.commit()

    async def get_generation(self, gen_id: str) -> Generation:
        result = await self.db.execute(
            select(Generation).where(Generation.id == gen_id)
        )
        gen = result.scalar_one_or_none()
        if not gen:
            raise GenerationNotFoundError(gen_id)
        return gen

    async def list_generations(
        self, offset: int = 0, limit: int = 50
    ) -> tuple[list[Generation], int]:
        query = select(Generation).order_by(Generation.created_at.desc())
        count_q = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_q)).scalar() or 0

        query = query.offset(offset).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all()), total

    async def delete_generation(self, gen_id: str) -> None:
        gen = await self.get_generation(gen_id)
        if gen.output_path:
            Path(gen.output_path).unlink(missing_ok=True)
        await self.db.delete(gen)
        await self.db.flush()

    async def delete_history(self) -> int:
        """Delete completed generations and their output files."""
        result = await self.db.execute(
            select(Generation).where(Generation.status == "completed")
        )
        generations = list(result.scalars().all())

        for gen in generations:
            if gen.output_path:
                Path(gen.output_path).unlink(missing_ok=True)
            await self.db.delete(gen)

        await self.db.flush()
        return len(generations)
