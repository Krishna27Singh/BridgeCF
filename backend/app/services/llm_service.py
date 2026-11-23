import json
import logging
import re
import time
from typing import Dict, Iterable, Optional

import requests

from ..config import get_settings


LOGGER = logging.getLogger("bridgecf.hints")

FORBIDDEN_PATTERNS = (
    r"\b(?:accepted|ac\s*solution|full\s*(?:solution|code)|here(?:'s|\s+is)\s+(?:the\s+)?(?:code|answer))\b",
)


class LLMError(RuntimeError):
    pass


def _safe_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value)).strip()


def guardrail_hint(text: str) -> str:
    text = _safe_text(text)
    if not text:
        raise LLMError("Provider returned an empty hint")
    if "```" in text or re.search(r"<code>|</code>", text, re.I):
        raise LLMError("Hint guardrail rejected code")
    if any(re.search(pattern, text, re.I) for pattern in FORBIDDEN_PATTERNS):
        raise LLMError("Hint guardrail rejected solution disclosure")
    return text[:1200]


def fallback_hint(problem_id: str, missing: Iterable[str], bridge_id: Optional[str]) -> Dict[str, str]:
    concepts = [str(item) for item in missing if item]
    if concepts:
        focus = concepts[0]
        message = (
            f"For {problem_id}, identify the role of {focus} before choosing operations."
        )
        next_step = f"State the main property of {focus} that applies to this problem."
    else:
        message = f"For {problem_id}, separate the observed constraints from the required result."
        next_step = "Write one invariant or case distinction you can verify."
    if bridge_id:
        next_step += f" Consider reviewing bridge problem {bridge_id} first."
    return {"message": message, "next_step": next_step, "level": "guided"}


class LLMHintService:
    def __init__(self, settings=None):
        self.settings = settings or get_settings()

    def _provider_name(self) -> str:
        provider = str(self.settings.llm_provider).strip().lower()
        aliases = {
            "openai": "openai-compatible",
            "openai_compatible": "openai-compatible",
            "google": "gemini",
            "local": "ollama",
        }
        return aliases.get(provider, provider)

    def _call_ollama(self, prompt: str) -> str:
        base = (self.settings.ollama_base_url or self.settings.llm_base_url).rstrip("/")
        model = self.settings.ollama_model or self.settings.llm_model
        response = requests.post(
            f"{base}/api/chat",
            json={
                "model": model,
                "stream": False,
                "messages": [
                    {"role": "system", "content": "Respond with a non-spoiler learning hint. Never provide the full solution or code."},
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
        key = self.settings.gemini_api_key or self.settings.llm_api_key
        if not key:
            raise LLMError("Gemini API key is not configured")
        model = self.settings.gemini_model
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
        response = requests.post(
            url,
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "responseMimeType": "application/json",
                },
            },
            timeout=self.settings.llm_timeout,
        )
        response.raise_for_status()
        parts = response.json().get("candidates", [{}])[0].get("content", {}).get("parts", [])
        return "".join(str(part.get("text", "")) for part in parts)

    def _call_openai(self, prompt: str) -> str:
        key = self.settings.openai_api_key or self.settings.llm_api_key
        if not key:
            raise LLMError("OpenAI-compatible API key is not configured")
        base = self.settings.openai_base_url.rstrip("/")
        model = self.settings.openai_model or self.settings.llm_model
        response = requests.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": "Respond as JSON with message and next_step fields. Give guidance only, never the full solution or code."},
                    {"role": "user", "content": prompt},
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.3,
            },
            timeout=self.settings.llm_timeout,
        )
        response.raise_for_status()
        return str(response.json()["choices"][0]["message"]["content"])

    def generate(self, problem_id: str, missing: Iterable[str], bridge_id: Optional[str]) -> Dict[str, object]:
        missing = [str(item) for item in missing]
        prompt = (
            f"Create a Socratic hint for Codeforces problem {problem_id}. "
            f"Missing concepts: {', '.join(missing) or 'none identified'}. "
            f"Bridge problem: {bridge_id or 'none'}. "
            "Do not reveal an answer or code. Return JSON with message and next_step."
        )
        provider = self._provider_name()
        retries = max(1, int(self.settings.llm_retries))
        last_error: Optional[Exception] = None

        for attempt in range(retries):
            try:
                if provider == "ollama":
                    raw = self._call_ollama(prompt)
                elif provider == "gemini":
                    raw = self._call_gemini(prompt)
                elif provider in ("openai-compatible", "openai"):
                    raw = self._call_openai(prompt)
                else:
                    break

                payload = json.loads(raw) if raw.strip().startswith("{") else {"message": raw}
                message = guardrail_hint(payload.get("message") or raw)
                next_step = guardrail_hint(payload.get("next_step") or "Try one small concrete case.")
                result = {
                    "level": payload.get("level") if payload.get("level") in ("guided", "nudge", "review") else "guided",
                    "message": message,
                    "next_step": next_step,
                    "missing_concepts": missing,
                    "bridge_problem_id": bridge_id,
                }
                LOGGER.info("hint_generated provider=%s problem_id=%s", provider, problem_id)
                return result
            except Exception as exc:
                last_error = exc
                LOGGER.warning("LLM attempt %d/%d failed for provider=%s: %s", attempt + 1, retries, provider, exc)
                if attempt + 1 < retries:
                    time.sleep(0.25 * (attempt + 1))

        fallback = fallback_hint(problem_id, missing, bridge_id)
        fallback.update({
            "missing_concepts": missing,
            "bridge_problem_id": bridge_id,
        })
        if last_error:
            LOGGER.info("hint_fallback problem_id=%s provider=%s reason=%s", problem_id, provider, last_error)
        else:
            LOGGER.info("hint_fallback problem_id=%s provider=%s", problem_id, provider)
        return fallback
