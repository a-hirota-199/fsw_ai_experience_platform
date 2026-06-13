"""要件構造化フロー（Sprint 0）。

自然言語の会話を1ステップ進め、情報不足なら確認質問を、十分なら構造化要件を返す。
LLM の担当はここ（非決定論）。出力は必ず JSON に制約し、解析はこちらで頑健に行う。
"""
from __future__ import annotations

import json
import logging
import re

from pydantic import ValidationError

from ..llm.client import get_provider
from ..llm.providers.base import LLMProvider
from ..models import ChatMessage, StructuredRequirement, StructureResponse

logger = logging.getLogger(__name__)

SYSTEM = """あなたは衛星FSW（cFS）の要件アナリスト。ユーザーと対話し、ミッション要件を
構造化された形（アプリ名・コマンド・テレメトリ・周期・テーブル）にまとめる。
情報が不足していれば1つだけ質問を返す。十分なら確定する。

出力は必ず次のJSONオブジェクトのみ（前後に説明文やコードフェンスを付けない）:
{
  "mode": "ask" | "final",
  "message": "ユーザーへの一文",
  "requirement": null | {
    "app_name": "小文字英数とアンダースコアのみ。例: att_app",
    "summary": "アプリの目的を一文で",
    "commands":  [{"name": "NOOP", "summary": "no-op"}],
    "telemetry": [{"name": "HK_TLM", "rate_hz": 1, "fields": ["cmd_count"]}],
    "tables":    ["param_table"],
    "open_questions": ["未確定事項"]
  }
}

厳守事項:
- requirement は mode=="final" のときだけ埋め、ask のときは null。
- requirement は **単一アプリの1オブジェクト**。複数アプリでも "apps":[...] でラップしない。
- フィールド名は app_name（name ではない）。tables は **文字列の配列**（オブジェクト不可）。
- rate_hz は数値（Hz）。fields は文字列の配列。"""


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
    raw_req = data.get("requirement")
    mode = data.get("mode", "ask")
    message = data.get("message", "")

    requirement = None
    if raw_req:
        coerced = _coerce_requirement(raw_req)
        try:
            requirement = StructuredRequirement(**coerced)
        except ValidationError as e:
            # 正規化しても合わない場合は体験を止めず、確認モードに退避する
            mode = "ask"
            message = message or "要件をうまく構造化できませんでした。アプリ名・コマンド・テレメトリ周期を一文で教えてください。"
            requirement = None
            _log_validation_miss(raw_req, e)

    return StructureResponse(mode=mode, message=message, requirement=requirement)


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


# --- LLM出力の正規化 ---------------------------------------------------------
# 実LLM（gemini/anthropic）はスキーマを厳密に守らないことがある。プロンプトで
# 形を指定しても、apps[] ラップ・name/app_name 揺れ・tables が dict 等が混ざる。
# ここで典型的なズレを吸収し、StructuredRequirement に通る形へ寄せる（決定論）。

_APP_NAME_ALIASES = ("app_name", "name", "app", "application", "appName", "app_id")


def _coerce_requirement(req: object) -> dict:
    """LLMが返したrequirementを StructuredRequirement に通る dict へ正規化する。"""
    if not isinstance(req, dict):
        return {}
    req = dict(req)  # 破壊的変更を避ける

    # 1) 単一要件を apps:[...] / applications:[...] でラップしてくる場合 → 先頭を採用
    for wrapper in ("apps", "applications"):
        items = req.get(wrapper)
        if "app_name" not in req and isinstance(items, list) and items and isinstance(items[0], dict):
            head = dict(items[0])
            # ラッパー直下にあった共通フィールド（summary等）も拾えるよう head を優先マージ
            req = {**{k: v for k, v in req.items() if k != wrapper}, **head}
            break

    # 2) app_name の別名吸収（name 等）
    if "app_name" not in req or not isinstance(req.get("app_name"), str):
        for alias in _APP_NAME_ALIASES:
            v = req.get(alias)
            if isinstance(v, str) and v.strip():
                req["app_name"] = v.strip()
                break

    # 3) summary 欠落の補完（required なので最低限埋める）
    if not isinstance(req.get("summary"), str) or not req.get("summary"):
        req["summary"] = req.get("description") or req.get("app_name") or "（要約未設定）"

    # 4) tables: dict/混在 → 文字列の配列へ
    req["tables"] = [_to_table_str(t) for t in _as_list(req.get("tables"))]

    # 5) commands / telemetry: 文字列要素やキー揺れを吸収
    req["commands"] = [_coerce_command(c) for c in _as_list(req.get("commands"))]
    req["commands"] = [c for c in req["commands"] if c]
    req["telemetry"] = [_coerce_telemetry(t) for t in _as_list(req.get("telemetry"))]
    req["telemetry"] = [t for t in req["telemetry"] if t]

    req["open_questions"] = [str(q) for q in _as_list(req.get("open_questions"))]
    return req


def _as_list(v: object) -> list:
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def _to_table_str(t: object) -> str:
    if isinstance(t, str):
        return t
    if isinstance(t, dict):
        for k in ("name", "table", "table_name", "id"):
            if isinstance(t.get(k), str) and t[k].strip():
                return t[k].strip()
        return json.dumps(t, ensure_ascii=False)
    return str(t)


def _coerce_command(c: object) -> dict | None:
    if isinstance(c, str):
        return {"name": c.strip()} if c.strip() else None
    if isinstance(c, dict):
        name = c.get("name") or c.get("command") or c.get("cmd")
        if not isinstance(name, str) or not name.strip():
            return None
        summary = c.get("summary") or c.get("description") or ""
        return {"name": name.strip(), "summary": str(summary)}
    return None


def _coerce_telemetry(t: object) -> dict | None:
    if isinstance(t, str):
        return {"name": t.strip()} if t.strip() else None
    if not isinstance(t, dict):
        return None
    name = t.get("name") or t.get("packet") or t.get("telemetry")
    if not isinstance(name, str) or not name.strip():
        return None
    out: dict = {"name": name.strip()}
    rate = t.get("rate_hz", t.get("rate", t.get("frequency_hz", t.get("hz"))))
    if isinstance(rate, (int, float)):
        out["rate_hz"] = rate
    elif isinstance(rate, str):
        m = re.search(r"[\d.]+", rate)
        if m:
            out["rate_hz"] = float(m.group())
    fields = t.get("fields", t.get("members"))
    out["fields"] = [str(f) for f in _as_list(fields)]
    return out


def _log_validation_miss(raw_req: object, err: ValidationError) -> None:
    """正規化しても通らなかったLLM出力をログに残す（体験は止めない）。"""
    logger.warning("requirement 正規化後も検証失敗: %s / raw=%s", err.errors(), raw_req)
