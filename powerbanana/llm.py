from __future__ import annotations

from .models import LLMSettings


def default_llm_settings() -> LLMSettings:
    return LLMSettings(
        provider="local",
        model="none",
        temperature=0.0,
        mode="deterministic_no_llm",
        max_tokens=0,
    )
