"""Google Gemini provider — swappable LLM 境界の実 provider（Claude の代替）。

- APIキーは環境変数（.env の `GEMINI_API_KEY` または `GOOGLE_API_KEY`）から解決する（BYOK）。
- モデルは `GEMINI_MODEL`（既定: gemini-2.5-flash）。
- Google 公式 `google-genai` SDK を使用（`from google import genai`）。
"""
from __future__ import annotations

import logging
import os
import time

from .base import LLMProvider

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-2.5-flash"
# 2.5系は思考が出力トークンを消費するため、空応答を避けるべく余裕を持たせる
DEFAULT_MAX_TOKENS = 8192

# 一時的エラー（過負荷/レート制限）はリトライで吸収する
_RETRYABLE_CODES = {429, 500, 502, 503, 504}
_MAX_RETRIES = 3       # 初回 + 最大3回の再試行
_BACKOFF_BASE_S = 1.0  # 1s, 2s, 4s の指数バックオフ


def _error_code(e: Exception) -> int | None:
    """SDK例外からHTTPステータスコードを取り出す（取れなければNone）。"""
    # google-genai の APIError は .code を持つ。無い実装/ラップ済みにも備える。
    code = getattr(e, "code", None) or getattr(e, "status_code", None)
    if isinstance(code, int):
        return code
    # メッセージ先頭の "503 UNAVAILABLE..." 形式からの救済
    head = str(e).strip()[:3]
    return int(head) if head.isdigit() else None


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

        resp = self._generate_with_retry(contents, config)
        return resp.text or ""

    def _generate_with_retry(self, contents: list, config: dict):
        """過負荷(503)/レート制限(429)等の一時的エラーを指数バックオフで再試行する。"""
        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                return self._client.models.generate_content(
                    model=self.model, contents=contents, config=config
                )
            except Exception as e:  # SDK例外型に依存せずHTTPコードで判定
                code = _error_code(e)
                if code not in _RETRYABLE_CODES or attempt == _MAX_RETRIES:
                    raise
                last_exc = e
                delay = _BACKOFF_BASE_S * (2**attempt)
                logger.warning(
                    "Gemini %s（code=%s）: %.0fs後に再試行 (%d/%d)",
                    "一時的エラー", code, delay, attempt + 1, _MAX_RETRIES,
                )
                time.sleep(delay)
        assert last_exc is not None  # 到達しない（ループ内でraise/returnする）
        raise last_exc
