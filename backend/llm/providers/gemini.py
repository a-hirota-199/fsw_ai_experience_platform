"""Google Gemini provider — swappable LLM 境界の実 provider（Claude の代替）。

- APIキーは環境変数（.env の `GEMINI_API_KEY` または `GOOGLE_API_KEY`）から解決する（BYOK）。
- モデルは `GEMINI_MODEL`（既定: gemini-2.5-flash）。
- Google 公式 `google-genai` SDK を使用（`from google import genai`）。
"""
from __future__ import annotations

import os

from .base import LLMProvider

DEFAULT_MODEL = "gemini-2.5-flash"
# 2.5系は思考が出力トークンを消費するため、空応答を避けるべく余裕を持たせる
DEFAULT_MAX_TOKENS = 8192


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, model: str | None = None, max_tokens: int = DEFAULT_MAX_TOKENS):
        key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not key:
            raise RuntimeError(
                "GEMINI_API_KEY（または GOOGLE_API_KEY）が未設定です。.env に設定してください"
                "（LLM_PROVIDER=gemini 使用時）。"
            )
        from google import genai  # 依存は利用時に解決（未導入環境でも他パスは動く）

        self._client = genai.Client(api_key=key)
        self.model = model or os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
        self.max_tokens = max_tokens

    def complete(self, messages: list[dict], *, system: str | None = None, **opts) -> str:
        # 共通の {role, content} を Gemini の contents（role は user/model）に変換
        contents = [
            {
                "role": "model" if m["role"] == "assistant" else "user",
                "parts": [{"text": m["content"]}],
            }
            for m in messages
        ]
        config: dict = {"max_output_tokens": opts.get("max_tokens", self.max_tokens)}
        if system:
            config["system_instruction"] = system

        resp = self._client.models.generate_content(
            model=self.model,
            contents=contents,
            config=config,
        )
        return resp.text or ""
