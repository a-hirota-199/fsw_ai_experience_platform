"""要件構造化フローの一周検証（Sprint 0、mock provider）。"""
import json

from backend.flow.structure import structure_step
from backend.llm.providers.mock import MockProvider
from backend.models import ChatMessage


def test_first_turn_asks():
    res = structure_step(
        [ChatMessage(role="user", content="衛星アプリ作りたい")],
        provider=MockProvider(),
    )
    assert res.mode == "ask"
    assert res.requirement is None
    assert res.message


def test_enough_info_finalizes():
    msgs = [
        ChatMessage(role="user", content="姿勢データを5Hzでテレメトリ送出したい"),
        ChatMessage(role="assistant", content="アプリ名は？"),
        ChatMessage(role="user", content="att_app。コマンドはNOOPとRESET。"),
    ]
    res = structure_step(msgs, provider=MockProvider())
    assert res.mode == "final"
    assert res.requirement is not None
    # 「5Hz」が周期として拾えていること（決定論モックの確認）
    assert any(t.rate_hz == 5 for t in res.requirement.telemetry)


def test_parse_is_robust_to_code_fence():
    from backend.flow.structure import _parse

    data = _parse('```json\n{"mode": "final", "message": "ok", "requirement": null}\n```')
    assert data["mode"] == "final"
    assert data["message"] == "ok"


# --- 実LLM（gemini等）のスキーマ揺れに対する正規化 ---

def test_coerce_unwraps_apps_and_aliases_name():
    from backend.flow.structure import _coerce_requirement
    from backend.models import StructuredRequirement

    # 実Geminiが落ちた形: apps[] でラップ + app_name でなく name + tables が dict
    raw = {
        "apps": [
            {
                "name": "NAV_APP",
                "summary": "地球周回の航法",
                "commands": [{"name": "NOOP", "summary": "no-op"}],
                "telemetry": [{"name": "HK", "rate_hz": 1, "fields": ["q0"]}],
                "tables": [{"app": "NAV_APP", "name": "nav_param", "default": 10}],
            }
        ]
    }
    req = StructuredRequirement(**_coerce_requirement(raw))  # 例外なく通ること
    assert req.app_name == "NAV_APP"
    assert req.summary == "地球周回の航法"
    assert req.tables == ["nav_param"]  # dict → 文字列


def test_coerce_fills_missing_summary_and_rate_aliases():
    from backend.flow.structure import _coerce_requirement
    from backend.models import StructuredRequirement

    raw = {
        "name": "att_app",  # app_name 欠落 → 別名で吸収
        "telemetry": [{"name": "ATT", "rate": "5 Hz", "fields": ["q0"]}],  # rate 別名＋文字列
        "tables": [],
    }
    req = StructuredRequirement(**_coerce_requirement(raw))
    assert req.app_name == "att_app"
    assert req.summary  # required: 何かしら埋まっている
    assert any(t.rate_hz == 5 for t in req.telemetry)


def test_structure_step_degrades_to_ask_on_unfixable_output():
    from backend.flow.structure import structure_step
    from backend.llm.providers.base import LLMProvider

    class BadProvider(LLMProvider):
        name = "bad"

        def complete(self, messages, *, system=None, **opts):
            # app_name を一切特定できない壊れた final
            return json.dumps({"mode": "final", "message": "done", "requirement": {"foo": "bar"}})

    res = structure_step([ChatMessage(role="user", content="x")], provider=BadProvider())
    # 500やトレースバックでなく、確認モードに退避していること
    assert res.mode == "ask"
    assert res.requirement is None
    assert res.message
