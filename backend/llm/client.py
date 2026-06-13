"""LLM provider のファクトリ。

`LLM_PROVIDER`（既定: mock）で provider を選ぶ。対応: mock / anthropic / gemini。
"""
from __future__ import annotations

import os

from .providers.base import LLMProvider
from .providers.mock import MockProvider


def get_provider(name: str | None = None) -> LLMProvider:
    name = (name or os.getenv("LLM_PROVIDER", "mock")).lower()
    if name == "mock":
        return MockProvider()
    if name == "anthropic":
        from .providers.anthropic import AnthropicProvider

        return AnthropicProvider()
    if name == "gemini":
        from .providers.gemini import GeminiProvider

        return GeminiProvider()
    raise ValueError(f"unknown LLM provider: {name}")
