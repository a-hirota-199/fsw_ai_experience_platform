"""Gemini provider のリトライ/エラーコード判定の検証（実API・google依存なし）。

GeminiProvider.__init__ は API キーと google パッケージを要求するため、
object.__new__ で生成をバイパスし、_client をフェイクに差し替えて検証する。
"""
import pytest

from backend.llm.providers import gemini as gm


class FakeErr(Exception):
    def __init__(self, code: int):
        super().__init__(f"{code} UNAVAILABLE. high demand")
        self.code = code


class FakeResp:
    text = "ok"


def _provider_with(generate):
    """generate_content を差し替えた GeminiProvider を __init__ 無しで作る。"""
    prov = object.__new__(gm.GeminiProvider)
    prov.model = "gemini-test"
    prov.max_tokens = 256

    class FakeModels:
        def generate_content(self, **kw):
            return generate(kw)

    class FakeClient:
        models = FakeModels()

    prov._client = FakeClient()
    return prov


def test_error_code_from_attr_and_message():
    assert gm._error_code(FakeErr(503)) == 503
    assert gm._error_code(Exception("503 UNAVAILABLE")) == 503
    assert gm._error_code(Exception("no code here")) is None


def test_retries_on_503_then_succeeds(monkeypatch):
    monkeypatch.setattr(gm.time, "sleep", lambda s: None)  # バックオフ待ちを無効化
    calls = {"n": 0}

    def gen(_kw):
        calls["n"] += 1
        if calls["n"] < 3:
            raise FakeErr(503)
        return FakeResp()

    prov = _provider_with(gen)
    resp = prov._generate_with_retry([], {})
    assert resp.text == "ok"
    assert calls["n"] == 3  # 2回失敗 → 3回目で成功


def test_does_not_retry_on_client_error(monkeypatch):
    monkeypatch.setattr(gm.time, "sleep", lambda s: None)
    calls = {"n": 0}

    def gen(_kw):
        calls["n"] += 1
        raise FakeErr(400)  # 4xx（リトライ対象外）は即時送出

    prov = _provider_with(gen)
    with pytest.raises(FakeErr):
        prov._generate_with_retry([], {})
    assert calls["n"] == 1


def test_gives_up_after_max_retries(monkeypatch):
    monkeypatch.setattr(gm.time, "sleep", lambda s: None)
    calls = {"n": 0}

    def gen(_kw):
        calls["n"] += 1
        raise FakeErr(503)  # 常に過負荷

    prov = _provider_with(gen)
    with pytest.raises(FakeErr):
        prov._generate_with_retry([], {})
    assert calls["n"] == gm._MAX_RETRIES + 1  # 初回 + リトライ回数
