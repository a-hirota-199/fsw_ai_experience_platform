"""LLM provider のファクトリ。

`LLM_PROVIDER`（既定: mock）で provider を選ぶ。anthropic provider は
Sprint 1+ で `providers/anthropic.py` を追加して有効化する。
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
        # Sprint 1+ で providers/anthropic.py を追加して有効化する
        raise NotImplementedError("anthropic provider は未実装（Sprint 1+ で追加）")
    raise ValueError(f"unknown LLM provider: {name}")
