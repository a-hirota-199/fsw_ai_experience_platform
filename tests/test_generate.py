"""コード生成フローの検証（Sprint 1、mock provider）。"""
from backend.flow.generate import generate_app
from backend.llm.providers.mock import MockProvider
from backend.models import CommandItem, StructuredRequirement, TelemetryItem


def _req():
    return StructuredRequirement(
        app_name="att_app",
        summary="姿勢テレメトリ送出",
        commands=[CommandItem(name="NOOP", summary="no-op"), CommandItem(name="RESET", summary="reset counters")],
        telemetry=[TelemetryItem(name="ATT_TLM", rate_hz=5, fields=["q0", "q1", "q2"])],
    )


def test_generate_produces_three_files():
    res = generate_app(_req(), provider=MockProvider())
    assert res.app_name == "att_app"
    paths = [f.path for f in res.files]
    assert any(p.endswith("att_app_app.c") for p in paths)
    assert any(p.endswith("att_app_app.h") for p in paths)
    assert any(p.endswith("CMakeLists.txt") for p in paths)


def test_header_has_telemetry_fields_and_command_codes():
    res = generate_app(_req(), provider=MockProvider())
    header = next(f.content for f in res.files if f.path.endswith(".h"))
    assert "q0" in header and "q1" in header and "q2" in header
    assert "ATT_APP_NOOP_CC" in header
    assert "ATT_APP_RESET_CC" in header


def test_source_has_dispatch_and_stub_holes():
    res = generate_app(_req(), provider=MockProvider())
    src = next(f.content for f in res.files if f.path.endswith("_app.c"))
    # 決定論側: コマンドのディスパッチが配線されている
    assert "ATT_APP_NOOP_CC" in src
    assert "ATT_APP_RESET(SBBufPtr)" in src
    # 非決定論側: mock では穴がスタブ化される
    assert "TODO(@LLM)" in src


def test_holes_are_filled_by_provider():
    class FillProvider(MockProvider):
        def complete(self, messages, *, system=None, **opts):
            import json
            return json.dumps(
                {"holes": {"cmd_NOOP": "CFE_EVS_SendEvent(0,0,\"NOOP\");"}, "notes": []},
                ensure_ascii=False,
            )

    res = generate_app(_req(), provider=FillProvider())
    src = next(f.content for f in res.files if f.path.endswith("_app.c"))
    assert 'CFE_EVS_SendEvent(0,0,"NOOP");' in src
