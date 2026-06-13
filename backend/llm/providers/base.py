"""swappable LLM 境界の最小インターフェース。

provider を差し替えても呼び出し側は変えない。BYOK/ローカルLLM は
このインターフェースを実装した provider を追加するだけで対応する。
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    def complete(
        self,
        messages: list[dict],
        *,
        system: str | None = None,
        **opts,
    ) -> str:
        """messages=[{role, content}] を受け取り、アシスタント応答テキストを返す。

        構造化出力が要る場合も、呼び出し側が system プロンプトで JSON を要求し、
        ここでは生テキストを返す（解析は呼び出し側の責務）。
        """
        raise NotImplementedError
