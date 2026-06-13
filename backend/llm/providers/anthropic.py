"""Anthropic (Claude) provider — swappable LLM 境界の実 provider。

- APIキーは環境変数（.env の `ANTHROPIC_API_KEY`）から解決する（BYOK）。
- モデルは `ANTHROPIC_MODEL`（既定: claude-opus-4-8）。最も高性能を試すなら claude-fable-5。
- 公式 `anthropic` SDK を使用（Pythonプロジェクトの既定）。
"""
from __future__ import annotations

import os

from .base import LLMProvider

DEFAULT_MODEL = "claude-opus-4-8"
DEFAULT_MAX_TOKENS = 4096


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, model: str | None = None, max_tokens: int = DEFAULT_MAX_TOKENS):
        if not (os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN")):
            raise RuntimeError(
                "ANTHROPIC_API_KEY が未設定です。.env に設定してください"
                "（LLM_PROVIDER=anthropic 使用時）。"
            )
        import anthropic  # 依存は利用時に解決（未導入環境でも mock パスは動く）

        self._client = anthropic.Anthropic()  # ANTHROPIC_API_KEY を環境から解決
        self.model = model or os.getenv("ANTHROPIC_MODEL", DEFAULT_MODEL)
        self.max_tokens = max_tokens

    def complete(self, messages: list[dict], *, system: str | None = None, **opts) -> str:
        kwargs: dict = {
            "model": self.model,
            "max_tokens": opts.get("max_tokens", self.max_tokens),
            "messages": [{"role": m["role"], "content": m["content"]} for m in messages],
        }
        if system:
            kwargs["system"] = system
        resp = self._client.messages.create(**kwargs)
        return "".join(b.text for b in resp.content if b.type == "text")
