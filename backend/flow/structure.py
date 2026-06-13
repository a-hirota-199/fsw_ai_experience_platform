"""要件構造化フロー（Sprint 0）。

自然言語の会話を1ステップ進め、情報不足なら確認質問を、十分なら構造化要件を返す。
LLM の担当はここ（非決定論）。出力は必ず JSON に制約し、解析はこちらで頑健に行う。
"""
from __future__ import annotations

import json

from ..llm.client import get_provider
from ..llm.providers.base import LLMProvider
from ..models import ChatMessage, StructuredRequirement, StructureResponse

SYSTEM = """あなたは衛星FSW（cFS）の要件アナリスト。ユーザーと対話し、ミッション要件を
構造化された形（アプリ名・コマンド・テレメトリ・周期・テーブル）にまとめる。
情報が不足していれば1つだけ質問を返す。十分なら確定する。
出力は必ず次のJSONのみ: {"mode": "ask"|"final", "message": str, "requirement": <obj|null>}
requirement は mode=="final" のときだけ埋める。"""


def structure_step(
    messages: list[ChatMessage],
    provider: LLMProvider | None = None,
) -> StructureResponse:
    """会話を1ステップ進め、確認質問 or 構造化要件を返す。"""
    provider = provider or get_provider()
    raw = provider.complete(
        [m.model_dump() for m in messages],
        system=SYSTEM,
    )
    data = _parse(raw)
    req = data.get("requirement")
    return StructureResponse(
        mode=data.get("mode", "ask"),
        message=data.get("message", ""),
        requirement=StructuredRequirement(**req) if req else None,
    )


def _parse(raw: str) -> dict:
    """LLM出力からJSONオブジェクトを取り出す（コードフェンス等に頑健に）。"""
    raw = (raw or "").strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            pass
    return {"mode": "ask", "message": raw or "もう少し詳しく教えてください。", "requirement": None}
