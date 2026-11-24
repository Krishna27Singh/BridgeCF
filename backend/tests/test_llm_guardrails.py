import requests

from app.config import Settings
from app.schemas import StructuredHint
from app.services.llm_service import (
    LLMHintService,
    _extract_json_object,
    detect_spoiler,
)


def test_valid_json_parses_to_structured_hint():
    hint = StructuredHint.model_validate(
        {
            "concept_tag": "dp",
            "conceptual_nudge": "What state does a prefix retain?",
            "strategy_hint": "Compare transitions for two neighboring prefix lengths.",
            "complexity_nudge": "Track the length and time bound implied by the constraints.",
            "bridge_rationale": "The bridge problem practices the same state-transition idea.",
        }
    )
    assert hint.concept_tag == "dp"


def test_fenced_json_extracts_to_structured_hint():
    fenced = """```json
{
  "concept_tag": "graphs",
  "conceptual_nudge": "Which edge state must persist?",
  "strategy_hint": "Track the frontier.",
  "complexity_nudge": "Use the constraints to choose O(V + E).",
  "bridge_rationale": "The bridge practices the same traversal."
}
```"""
    hint = StructuredHint.model_validate(
        __import__("json").loads(_extract_json_object(fenced))
    )
    assert hint.concept_tag == "graphs"


def test_settings_accepts_comma_separated_cors_origins(monkeypatch):
    monkeypatch.setenv(
        "CORS_ORIGINS",
        "http://127.0.0.1:8000,https://codeforces.com",
    )
    settings = Settings()
    assert settings.cors_origins == [
        "http://127.0.0.1:8000",
        "https://codeforces.com",
    ]


def test_spoiler_detector_rejects_code_and_signatures():
    assert detect_spoiler("```cpp\nint main() {}\n```")
    assert detect_spoiler("int main() { return 0; }")
    assert detect_spoiler("def solve():")
    assert detect_spoiler("#include <bits/stdc++.h>")


def test_guardrail_corrective_retry(monkeypatch):
    settings = type(
        "Settings",
        (),
        {
            "llm_provider": "openai_compat",
            "openai_api_key": "test",
            "openai_base_url": "https://example.invalid/v1",
            "openai_model": "test",
            "llm_timeout": 1,
            "llm_retries": 2,
        },
    )()
    service = LLMHintService(settings)
    responses = [
        (
            '{"concept_tag":"dp","conceptual_nudge":"```","strategy_hint":"x",'
            '"complexity_nudge":"x","bridge_rationale":"x"}'
        ),
        (
            '{"concept_tag":"dp","conceptual_nudge":"What state is retained?",'
            '"strategy_hint":"Compare transitions.","complexity_nudge":"O(n).",'
            '"bridge_rationale":"The bridge practices transitions."}'
        ),
    ]

    monkeypatch.setattr(service, "_call_openai", lambda prompt: responses.pop(0))
    hint, provider, fallback_used = service.generate(
        "1_A",
        ["dp"],
        {"problem_id": "1_B", "rating": 900},
        {"name": "Test", "rating": 1000, "tags": ["dp"], "statement": ""},
    )
    assert not fallback_used
    assert provider == "openai_compat"
    assert hint.concept_tag == "dp"


def test_graceful_fallback_on_connection_error(monkeypatch):
    settings = type(
        "Settings",
        (),
        {
            "llm_provider": "ollama",
            "ollama_base_url": "http://127.0.0.1:9",
            "ollama_model": "test",
            "llm_timeout": 0.1,
            "llm_retries": 2,
            "gemini_api_key": "",
            "gemini_model": "test",
            "openai_api_key": "",
            "openai_base_url": "http://127.0.0.1",
            "openai_model": "test",
        },
    )()
    service = LLMHintService(settings)

    def fail(_prompt):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr(service, "_call_ollama", fail)
    hint, provider, fallback_used = service.generate(
        "1_A",
        ["graphs"],
        {"problem_id": "1_B", "rating": 900},
        {"name": "Test", "rating": 1000, "tags": ["graphs"], "statement": ""},
    )
    assert fallback_used
    assert provider == "fallback"
    assert hint.concept_tag == "graphs"
