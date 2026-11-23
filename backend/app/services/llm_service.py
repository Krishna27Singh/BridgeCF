import json
import logging
import re
import time
from typing import Iterable, Optional

import requests
from pydantic import ValidationError

from ..config import get_settings
from ..schemas import StructuredHint

LOGGER = logging.getLogger("bridgecf.hints")


def detect_spoiler(text: str) -> Optional[str]:
    if "```" in text:
        return "Code fences are not allowed"
    if re.search(r"\bint\s+main\s*\(", text, re.I):
        return "C++ solution signature is not allowed"
    if re.search(r"\bdef\s+solve\s*\(", text, re.I):
        return "Python solution signature is not allowed"
    if re.search(r"#include\s*[<\"]", text, re.I):
        return "Include directives are not allowed"
    return None


def fallback_hint(problem_id: str, missing: Iterable[str], bridge_id: Optional[str]):
    concept = next((str(item) for item in missing if item), "the main constraint")
    return StructuredHint(
        concept_tag=concept,
        conceptual_nudge=f"Which invariant or required observation makes {problem_id} solvable?",
        strategy_hint=f"First isolate how {concept} changes the allowed operations.",
        complexity_nudge=(
            "Compare candidate data structures against the target constraint limits."
        ),
        bridge_rationale=(
            f"{bridge_id or 'The recommended bridge problem'} provides practice on "
            f"the prerequisite skill {concept} before tackling {problem_id}."
        ),
    )


class LLMHintService:
    def __init__(self, settings=None):
        self.settings = settings or get_settings()

    def _call_ollama(self, prompt: str) -> str:
        response = requests.post(
            f"{self.settings.ollama_base_url.rstrip('/')}/api/chat",
            json={
                "model": self.settings.ollama_model,
                "stream": False,
                "messages": [
                    {"role": "system", "content": "Return only structured non-spoiler hint JSON."},
                    {"role": "user", "content": prompt},
                ],
                "format": "json",
            },
            timeout=self.settings.llm_timeout,
        )
        response.raise_for_status()
        data = response.json()
        return str(data.get("message", {}).get("content") or data.get("response") or "")

    def _call_gemini(self, prompt: str) -> str:
        if not self.settings.gemini_api_key:
            raise RuntimeError("Gemini API key is not configured")
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.settings.gemini_model}:generateContent"
            f"?key={self.settings.gemini_api_key}"
        )
        response = requests.post(
            url,
            json={"contents": [{"parts": [{"text": prompt}]}]},
            timeout=self.settings.llm_timeout,
        )
        response.raise_for_status()
        parts = response.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
        return "".join(str(part.get("text", "")) for part in parts)

    def _call_openai(self, prompt: str) -> str:
        if not self.settings.openai_api_key:
            raise RuntimeError("OpenAI-compatible API key is not configured")
        response = requests.post(
            f"{self.settings.openai_base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {self.settings.openai_api_key}"},
            json={
                "model": self.settings.openai_model,
                "messages": [
                    {"role": "system", "content": "Return only the requested JSON hint schema."},
                    {"role": "user", "content": prompt},
                ],
                "response_format": {"type": "json_object"},
            },
            timeout=self.settings.llm_timeout,
        )
        response.raise_for_status()
        return str(response.json()["choices"][0]["message"]["content"])

    def generate(
        self,
        problem_id: str,
        missing: Iterable[str],
        bridge,
        target_metadata: dict,
    ) -> tuple[StructuredHint, str, bool]:
        missing_list = [str(item) for item in missing]
        bridge_id = bridge.get("problem_id") if bridge else None
        bridge_rating = bridge.get("rating") if bridge else None
        metadata_text = json.dumps(
            {
                "name": target_metadata.get("name"),
                "rating": target_metadata.get("rating"),
                "tags": target_metadata.get("tags", []),
                "statement_snippet": (target_metadata.get("statement") or "")[:700],
                "missing_concepts": missing_list,
                "bridge_problem": {
                    "problem_id": bridge_id,
                    "rating": bridge_rating,
                },
            },
            ensure_ascii=False,
        )
        prompt = (
            "Use the context below to produce exactly a StructuredHint JSON object. "
            "Never provide code, an accepted solution, or a complete answer.\n"
            f"Context: {metadata_text}\n"
            "Required keys: concept_tag, conceptual_nudge, strategy_hint, "
            "complexity_nudge, bridge_rationale."
        )
        provider = self.settings.llm_provider.lower()
        last_error = "provider offline"

        for attempt in range(2):
            try:
                if provider == "ollama":
                    raw = self._call_ollama(prompt)
                elif provider == "gemini":
                    raw = self._call_gemini(prompt)
                elif provider in ("openai_compat", "openai-compatible", "openai"):
                    raw = self._call_openai(prompt)
                else:
                    break

                payload = json.loads(raw)
                hint = StructuredHint.model_validate(payload)
                spoiler_error = next(
                    (
                        detect_spoiler(value)
                        for value in hint.model_dump().values()
                        if isinstance(value, str) and detect_spoiler(value)
                    ),
                    None,
                )
                if spoiler_error:
                    raise RuntimeError(spoiler_error)
                return hint, provider, False
            except (
                ValidationError,
                json.JSONDecodeError,
                RuntimeError,
                requests.RequestException,
            ) as exc:
                last_error = str(exc)
                LOGGER.warning("LLM attempt %d failed: %s", attempt + 1, exc)
                prompt = prompt + f"\nCorrect the previous output. Validation error: {last_error}"
                time.sleep(0.05)

        LOGGER.info("Using deterministic hint fallback: %s", last_error)
        return fallback_hint(problem_id, missing_list, bridge_id), "fallback", True
