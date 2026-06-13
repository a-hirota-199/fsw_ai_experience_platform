"""コード生成フロー（Sprint 1）。

構造化要件 → cFSアプリのコード。骨格・配線・MIDは決定論テンプレ（templates/cfs_app.py）で固定し、
LLM には「穴（業務ロジック）」だけを埋めさせる。LLMが埋めなかった穴はスタブで補完する。
"""
from __future__ import annotations

import json

from ..llm.client import get_provider
from ..llm.providers.base import LLMProvider
from ..models import GenerateResponse, StructuredRequirement
from ..templates import cfs_app

# mock provider が「生成リクエスト」を判別するためのマーカー（system 内に含める）
GEN_MARKER = "GENERATE_APP"

SYSTEM = (
    "あなたは cFS（core Flight System）アプリのC実装者。\n"
    "骨格・配線・MID・テレメトリ構造体は決定論ツールが生成済みで、あなたは「穴」（業務ロジック）だけを埋める。\n"
    "各穴に入れるCコード本体のみを返す（関数シグネチャや骨格は含めない）。\n"
    '出力は必ず次のJSONのみ: {"holes": {"<hole_id>": "<C code body>"}, "notes": ["..."]}\n'
    f"{GEN_MARKER}"
)


def generate_app(
    req: StructuredRequirement,
    provider: LLMProvider | None = None,
) -> GenerateResponse:
    provider = provider or get_provider()
    specs = cfs_app.hole_specs(req)

    raw = provider.complete([{"role": "user", "content": _build_prompt(req, specs)}], system=SYSTEM)
    data = _extract_json(raw)
    llm_holes = data.get("holes", {}) if isinstance(data, dict) else {}
    notes = list(data.get("notes", [])) if isinstance(data, dict) else []

    holes: dict[str, str] = {}
    stubbed: list[str] = []
    for hid, desc in specs.items():
        code = llm_holes.get(hid)
        if not code or not str(code).strip():
            code = f"/* TODO(@LLM): {desc} */"
            stubbed.append(hid)
        holes[hid] = str(code)
    if stubbed:
        notes.append("未生成のホールをスタブ化: " + ", ".join(stubbed))

    files = cfs_app.render(req, holes)
    return GenerateResponse(app_name=req.app_name, files=files, notes=notes)


def _build_prompt(req: StructuredRequirement, specs: dict[str, str]) -> str:
    lines = [
        "# 構造化要件",
        json.dumps(req.model_dump(), ensure_ascii=False, indent=2),
        "",
        "# 埋める穴（hole_id: 説明）",
    ]
    lines += [f"- {hid}: {desc}" for hid, desc in specs.items()]
    lines += [
        "",
        "各 hole_id に入れるCコード本体だけを holes に入れて返してください。",
        "テレメトリのフィールド名は要件の telemetry.fields に一致させること。",
    ]
    return "\n".join(lines)


def _extract_json(raw: str) -> dict:
    raw = (raw or "").strip()
    s, e = raw.find("{"), raw.rfind("}")
    if s != -1 and e != -1 and e > s:
        try:
            return json.loads(raw[s : e + 1])
        except json.JSONDecodeError:
            pass
    return {}
