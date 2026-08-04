from __future__ import annotations
import asyncio
import json
import logging
from typing import Optional

import google.generativeai as genai

from config import get_settings
from models.schemas import LLMResponse, CorrectionPayload, ObservationsPayload
from prompts.system_prompt import get_system_prompt, GREETING_PROMPT
from services.usage_tracker import usage_tracker
from services.user_memory import user_memory

logger = logging.getLogger(__name__)
settings = get_settings()

genai.configure(api_key=settings.gemini_api_key)

# Ordered fallback list — exhausted models are skipped automatically
MODEL_CHAIN = [
    {"name": "gemini-2.0-flash",          "daily_limit": 1500},
    {"name": "gemini-2.0-flash-lite",     "daily_limit": 1500},
    {"name": "gemini-flash-lite-latest",  "daily_limit": 1500},
    {"name": "gemini-2.5-flash-lite",     "daily_limit": 500},
    {"name": "gemini-2.5-flash",          "daily_limit": 20},
]


def _is_quota_error(exc: Exception) -> bool:
    msg = str(exc)
    return "429" in msg or "ResourceExhausted" in msg or "quota" in msg.lower()


class LLMEngine:
    """Wrapper around Gemini API with automatic model fallback on quota exhaustion."""

    def __init__(self):
        self._model_idx = 0
        self._sync_limit()

    def _sync_limit(self):
        usage_tracker.daily_limit = MODEL_CHAIN[self._model_idx]["daily_limit"]

    def _current_model_name(self) -> str:
        return MODEL_CHAIN[self._model_idx]["name"]

    def _advance_model(self) -> bool:
        if self._model_idx < len(MODEL_CHAIN) - 1:
            self._model_idx += 1
            self._sync_limit()
            logger.warning(f"Model quota hit — switched to {self._current_model_name()}")
            return True
        logger.error("All models exhausted for today")
        return False

    def _make_model(self) -> genai.GenerativeModel:
        system_prompt = get_system_prompt(user_memory.to_context_string())
        return genai.GenerativeModel(
            model_name=self._current_model_name(),
            generation_config=genai.types.GenerationConfig(
                max_output_tokens=settings.gemini_max_tokens,
                temperature=settings.gemini_temperature,
            ),
            system_instruction=system_prompt,
        )

    async def _call_with_fallback(self, fn) -> any:
        """Run fn (a sync callable) with automatic model fallback on 429."""
        while True:
            try:
                return await asyncio.to_thread(fn)
            except Exception as e:
                if _is_quota_error(e) and self._advance_model():
                    continue
                raise

    async def chat(self, user_message: str, history: list[dict], session_id: str = "") -> LLMResponse:
        gemini_history = [
            {"role": turn["role"], "parts": [turn["content"]]} for turn in history
        ]

        def _send():
            model = self._make_model()
            chat = model.start_chat(history=gemini_history)
            return chat.send_message(user_message)

        response = await self._call_with_fallback(_send)
        self._record_usage(response, session_id)
        return self._parse_response(response.text)

    async def generate_greeting(self, session_id: str = "") -> LLMResponse:
        def _send():
            model = self._make_model()
            chat = model.start_chat(history=[])
            return chat.send_message(GREETING_PROMPT)

        response = await self._call_with_fallback(_send)
        self._record_usage(response, session_id)
        return self._parse_response(response.text)

    async def generate_reflection(
        self,
        transcript: str,
        weaknesses_summary: str,
        reflection_prompt: str,
    ) -> dict:
        """Generate a post-session reflection using the full transcript."""
        prompt = f"""{reflection_prompt}

## Conversation Transcript
{transcript}

## Aggregated Weakness Observations
{weaknesses_summary}
"""
        def _make_reflection_model():
            return genai.GenerativeModel(
                model_name=self._current_model_name(),
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=2048,
                    temperature=0.7,
                ),
            )

        raw_text = await self._call_with_fallback(
            lambda: _make_reflection_model().generate_content(prompt).text
        )
        return self._parse_json_block(raw_text) or {}

    def _record_usage(self, response, session_id: str):
        try:
            meta = response.usage_metadata
            usage_tracker.record(
                session_id=session_id,
                tokens_in=meta.prompt_token_count or 0,
                tokens_out=meta.candidates_token_count or 0,
                model_name=self._current_model_name(),
            )
        except Exception:
            pass

    def _parse_response(self, raw_text: str) -> LLMResponse:
        parsed = self._parse_json_block(raw_text)

        if parsed is None:
            logger.warning("Failed to parse JSON from LLM, using raw text as reply")
            return LLMResponse(
                reply=raw_text.strip(),
                correction=None,
                observations=ObservationsPayload(),
            )

        correction = None
        if parsed.get("correction"):
            c = parsed["correction"]
            correction = CorrectionPayload(
                original=c.get("original", ""),
                improved=c.get("improved", ""),
                note=c.get("note", ""),
            )

        obs_data = parsed.get("observations") or {}
        observations = ObservationsPayload(
            grammar_errors=obs_data.get("grammar_errors", []),
            filler_words=obs_data.get("filler_words", []),
            awkward_phrasing=obs_data.get("awkward_phrasing", []),
            vocab_gaps=obs_data.get("vocab_gaps", []),
            confidence_signal=obs_data.get("confidence_signal", "medium"),
            fluency_signal=obs_data.get("fluency_signal", "smooth"),
            tone_appropriateness=obs_data.get("tone_appropriateness", "appropriate"),
        )

        learned_facts = parsed.get("learned_facts") or []
        if isinstance(learned_facts, list):
            learned_facts = [f for f in learned_facts if isinstance(f, str) and f.strip()]
        else:
            learned_facts = []

        return LLMResponse(
            reply=parsed.get("reply", raw_text.strip()),
            correction=correction,
            learned_facts=learned_facts,
            observations=observations,
        )

    def _parse_json_block(self, text: str) -> Optional[dict]:
        text = text.strip()

        if text.startswith("```"):
            lines = text.split("\n")[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start != -1 and end > start:
                try:
                    return json.loads(text[start:end])
                except json.JSONDecodeError:
                    pass

        logger.error(f"Could not parse JSON from LLM response: {text[:200]}...")
        return None


# Singleton
llm_engine = LLMEngine()
