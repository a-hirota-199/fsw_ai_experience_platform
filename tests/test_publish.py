"""GitHub 公開フローの検証（Sprint 1 後半）。

mock provider はキー不要で一周を検証。実GitHub provider は requests.Session を
フェイクに差し替え、実APIもネットワークも使わずに呼び出し列を検証する。
"""
import json

import pytest

from backend.integrations import github as gh
from backend.integrations.base import slug_branch
from backend.integrations.client import get_github
from backend.integrations.mock import MockGitHub
from backend.models import GeneratedFile


def _files():
    return [
        GeneratedFile(path="att_app/fsw/src/att_app_app.c", content="/* c */"),
        GeneratedFile(path="att_app/fsw/src/att_app_app.h", content="/* h */"),
        GeneratedFile(path="att_app/CMakeLists.txt", content="# cmake"),
    ]


# --- mock & client ----------------------------------------------------------

def test_mock_publish_returns_pr():
    res = MockGitHub().publish_app("att_app", _files(), summary="姿勢テレメトリ")
    assert res.ok is True
    assert res.branch == "feat/att_app"
    assert res.pr_url.endswith("/pull/1")
    assert len(res.notes) == 3


def test_client_defaults_to_mock(monkeypatch):
    monkeypatch.delenv("GITHUB_PROVIDER", raising=False)
    assert isinstance(get_github(), MockGitHub)


def test_client_unknown_provider_raises(monkeypatch):
    with pytest.raises(ValueError):
        get_github("svn")


def test_slug_branch_sanitizes():
    assert slug_branch("ATT App!") == "att-app"
    assert slug_branch("") == "app"


# --- real GitHub provider（フェイクSession） --------------------------------

class FakeResp:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload
        self.text = "" if payload is None else json.dumps(payload)

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


class FakeSession:
    """GitHub REST の最小ルーティング。呼び出し列を calls に記録する。"""

    def __init__(self):
        self.headers = {}
        self.calls = []

    def _route(self, method, url):
        self.calls.append((method, url))
        if method == "GET" and url.endswith("/repos/o/r"):
            return FakeResp(200, {"default_branch": "main"})
        if method == "GET" and url.endswith("/git/ref/heads/main"):
            return FakeResp(200, {"object": {"sha": "base-sha"}})
        if method == "GET" and "/git/ref/heads/feat/att_app" in url:
            return FakeResp(404, {"message": "Not Found"})  # ブランチ未存在
        if method == "POST" and url.endswith("/git/refs"):
            return FakeResp(201, {"ref": "refs/heads/feat/att_app"})
        if method == "PUT" and "/contents/" in url:
            return FakeResp(201, {"content": {"path": url.split("/contents/")[-1]}})
        if method == "POST" and url.endswith("/pulls"):
            return FakeResp(201, {"html_url": "https://github.com/o/r/pull/7", "number": 7})
        return FakeResp(404, {"message": "unmatched"})

    def request(self, method, url, **kw):
        return self._route(method, url)

    def get(self, url, **kw):
        return self._route("GET", url)

    def put(self, url, **kw):
        return self._route("PUT", url)

    def post(self, url, **kw):
        return self._route("POST", url)


def _real_provider(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    monkeypatch.setenv("GITHUB_REPO", "o/r")
    monkeypatch.delenv("GITHUB_API", raising=False)
    prov = gh.RealGitHub()
    prov._s = FakeSession()  # 実Sessionをフェイクに差し替え
    return prov


def test_real_github_requires_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)
    monkeypatch.setenv("GITHUB_REPO", "o/r")
    with pytest.raises(RuntimeError):
        gh.RealGitHub()


def test_real_github_requires_valid_repo(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    monkeypatch.setenv("GITHUB_REPO", "no-slash")
    with pytest.raises(RuntimeError):
        gh.RealGitHub()


def test_empty_github_api_falls_back_to_default(monkeypatch):
    # .env に GITHUB_API= とだけ書かれた（空文字）場合でも既定URLになること
    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    monkeypatch.setenv("GITHUB_REPO", "o/r")
    monkeypatch.setenv("GITHUB_API", "")
    prov = gh.RealGitHub()
    assert prov.api == gh.DEFAULT_API
    assert prov._url("") == f"{gh.DEFAULT_API}/repos/o/r"  # スキーム付きの正しいURL


def test_repo_404_gives_access_guidance(monkeypatch):
    prov = _real_provider(monkeypatch)

    class Fake404:
        headers = {}

        def get(self, url, **kw):
            return FakeResp(404, {"message": "Not Found"})

    prov._s = Fake404()
    with pytest.raises(RuntimeError) as ei:
        prov._default_branch()
    assert "アクセス" in str(ei.value)  # 生の404でなく権限ガイダンス


class FakeEmptyRepoSession:
    """空リポジトリ → 初期化(README) → 公開、の状態遷移を模す。"""

    def __init__(self):
        self.headers = {}
        self.calls = []
        self.initialized = False  # README bootstrap 済みか

    def _route(self, method, url):
        self.calls.append((method, url))
        if method == "GET" and url.endswith("/repos/o/r"):
            return FakeResp(200, {"default_branch": "main"})
        if method == "GET" and url.endswith("/git/ref/heads/main"):
            if not self.initialized:
                return FakeResp(409, {"message": "Git Repository is empty."})
            return FakeResp(200, {"object": {"sha": "init-sha"}})
        if method == "PUT" and url.endswith("/contents/README.md"):
            self.initialized = True  # 初期コミットで main が生える
            return FakeResp(201, {"content": {"path": "README.md"}})
        if method == "GET" and "/git/ref/heads/feat/att_app" in url:
            return FakeResp(404, {"message": "Not Found"})
        if method == "POST" and url.endswith("/git/refs"):
            return FakeResp(201, {})
        if method == "PUT" and "/contents/" in url:
            return FakeResp(201, {"content": {}})
        if method == "POST" and url.endswith("/pulls"):
            return FakeResp(201, {"html_url": "https://github.com/o/r/pull/1"})
        return FakeResp(404, {"message": "unmatched"})

    def request(self, method, url, **kw):
        return self._route(method, url)

    def get(self, url, **kw):
        return self._route("GET", url)

    def put(self, url, **kw):
        return self._route("PUT", url)

    def post(self, url, **kw):
        return self._route("POST", url)


def test_publish_bootstraps_empty_repo(monkeypatch):
    prov = _real_provider(monkeypatch)
    prov._s = FakeEmptyRepoSession()
    res = prov.publish_app("att_app", _files(), summary="姿勢テレメトリ")

    assert res.ok is True
    assert res.pr_url.endswith("/pull/1")
    # 空repo初期化のため README を1コミットしていること
    assert any(m == "PUT" and u.endswith("/contents/README.md") for m, u in prov._s.calls)
    # 生成物3ファイルは feature ブランチにコミットされること（READMEは notes に含めない）
    assert len(res.notes) == 3


def test_real_github_publish_creates_branch_files_and_pr(monkeypatch):
    prov = _real_provider(monkeypatch)
    res = prov.publish_app("att_app", _files(), summary="姿勢テレメトリ")

    assert res.ok is True
    assert res.repo == "o/r"
    assert res.branch == "feat/att_app"
    assert res.pr_url == "https://github.com/o/r/pull/7"
    assert len(res.notes) == 3

    methods = [m for m, _ in prov._s.calls]
    # ブランチ作成1回・ファイルPUT3回・PR作成1回が含まれること
    assert ("POST", f"{gh.DEFAULT_API}/repos/o/r/git/refs") in prov._s.calls
    assert methods.count("PUT") == 3
    assert ("POST", f"{gh.DEFAULT_API}/repos/o/r/pulls") in prov._s.calls
