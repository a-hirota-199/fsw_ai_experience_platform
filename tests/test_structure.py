"""要件構造化フローの一周検証（Sprint 0、mock provider）。"""
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
