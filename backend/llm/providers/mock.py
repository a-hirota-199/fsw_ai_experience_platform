"""キー不要の決定論モック provider。

要件構造化フローの一周（チャット→構造化JSON）を、APIキー無しで検証するためのもの。
structure フローの system プロンプトに合わせ、JSON {mode, message, requirement} を返す。
"""
from __future__ import annotations

import json
import re

from .base import LLMProvider


class MockProvider(LLMProvider):
    name = "mock"

    def complete(self, messages: list[dict], *, system: str | None = None, **opts) -> str:
        # コード生成リクエストは穴を空で返す（generate側がスタブで補完する）
        if system and "GENERATE_APP" in system:
            return json.dumps(
                {"holes": {}, "notes": ["（mock）穴は未生成スタブ。実LLM(gemini/anthropic)で埋まります"]},
                ensure_ascii=False,
            )

        user_turns = [m for m in messages if m.get("role") == "user"]
        last = user_turns[-1]["content"] if user_turns else ""

        # 1ターン目は確認質問、2ターン目以降は構造化を確定（決定論）
        if len(user_turns) < 2:
            return json.dumps(
                {
                    "mode": "ask",
                    "message": "対象アプリ名と、テレメトリの送出周期（Hz）、必要なコマンドを教えてください。",
                    "requirement": None,
                },
                ensure_ascii=False,
            )

        return json.dumps(
            {
                "mode": "final",
                "message": "要件を構造化しました。内容を確認してください。",
                "requirement": _mock_requirement(last, user_turns),
            },
            ensure_ascii=False,
        )


def _mock_requirement(text: str, user_turns: list[dict]) -> dict:
    joined = " ".join(t.get("content", "") for t in user_turns)
    rate = _guess_rate(joined)
    return {
        "app_name": "sample_tlm_app",
        "summary": (text or "衛星アプリ要件")[:120],
        "commands": [
            {"name": "NOOP", "summary": "no-op コマンド"},
            {"name": "RESET_COUNTERS", "summary": "カウンタ初期化"},
        ],
        "telemetry": [
            {"name": "HK_TLM", "rate_hz": 1, "fields": ["cmd_count", "err_count"]},
            {"name": "ATT_TLM", "rate_hz": rate, "fields": ["q0", "q1", "q2", "q3"]},
        ],
        "tables": [],
        "open_questions": ["テレメトリのパケット長は確定か？"],
    }


def _guess_rate(text: str) -> int:
    m = re.search(r"(\d+)\s*hz", text.lower())
    return int(m.group(1)) if m else 1
