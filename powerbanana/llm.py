from __future__ import annotations

import os
from collections.abc import Mapping

from .models import LLMSettings
from .vocabulary import LLMVocabularyAdvisor, NullVocabularyAdvisor


def default_llm_settings() -> LLMSettings:
    return LLMSettings(
        provider="local",
        model="none",
        temperature=0.0,
        mode="deterministic_no_llm",
        max_tokens=0,
    )


def vocabulary_advisor_from_env(environ: Mapping[str, str] | None = None) -> LLMVocabularyAdvisor:
    env = os.environ if environ is None else environ
    provider = env.get("POWERBANANA_VOCAB_ADVISOR", "").strip().lower()
    if provider in {"", "none", "off", "disabled", "null"}:
        return NullVocabularyAdvisor()
    if provider != "openai":
        raise ValueError(f"Unsupported POWERBANANA_VOCAB_ADVISOR provider: {provider}")

    api_key = env.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("OPENAI_API_KEY is required when POWERBANANA_VOCAB_ADVISOR=openai.")

    from .llm_vocabulary import JsonLLMVocabularyAdvisor, OpenAIResponsesJsonClient

    model = env.get("POWERBANANA_VOCAB_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    base_url = env.get("POWERBANANA_VOCAB_BASE_URL", "https://api.openai.com/v1").strip() or "https://api.openai.com/v1"
    timeout_seconds = _env_float(env, "POWERBANANA_VOCAB_TIMEOUT_SECONDS", 30.0)
    temperature = _env_float(env, "POWERBANANA_VOCAB_TEMPERATURE", 0.0)
    max_tokens = _env_int(env, "POWERBANANA_VOCAB_MAX_TOKENS", 500)
    client = OpenAIResponsesJsonClient(
        api_key=api_key,
        base_url=base_url,
        timeout_seconds=timeout_seconds,
    )
    return JsonLLMVocabularyAdvisor(
        client=client,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )


def _env_float(env: Mapping[str, str], key: str, default: float) -> float:
    value = env.get(key)
    if value is None or not value.strip():
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _env_int(env: Mapping[str, str], key: str, default: int) -> int:
    value = env.get(key)
    if value is None or not value.strip():
        return default
    try:
        return int(value)
    except ValueError:
        return default
