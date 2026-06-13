"""実GitHub provider — 指定repoに branch を切り、生成物をコミットして PR を起票する。

設定（.env, BYOK）:
  GITHUB_PROVIDER=github
  GITHUB_TOKEN=ghp_...               # repo スコープの PAT（fine-grained なら contents:write + pull_requests:write）
  GITHUB_REPO=owner/name             # 公開先の既存リポジトリ（サンドボックス想定）
  GITHUB_API=https://api.github.com  # 省略可（GitHub Enterprise 時に変更）

フロー（branch+PR）:
  1. 既定ブランチ（base）と先端 SHA を取得
  2. feat/<app> ブランチを base から作成（衝突時は -2, -3... を試す）
  3. 各ファイルを Contents API でブランチにコミット（既存ファイルは sha 付きで更新）
  4. base 宛に PR を起票（既存PRがあれば再利用）
"""
from __future__ import annotations

import base64
import logging
import os

import requests

from .base import GitHubIntegration, slug_branch
from ..models import GeneratedFile, PublishResponse

logger = logging.getLogger(__name__)

DEFAULT_API = "https://api.github.com"
_TIMEOUT = 30

_INIT_README = (
    "# sandbox\n\n"
    "AI駆動FSW開発プラットフォーム（体験版）の生成物公開先リポジトリ。\n"
    "このコミットは空リポジトリ初期化のために自動作成されました。\n"
)


class RealGitHub(GitHubIntegration):
    name = "github"

    def __init__(self) -> None:
        self.token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
        self.repo = os.getenv("GITHUB_REPO", "")
        # 空文字（.env に GITHUB_API= とだけ書かれた場合）も既定にフォールバックさせる。
        # os.getenv の既定値は「未設定時」のみ効くため、or で空文字も拾う。
        self.api = (os.getenv("GITHUB_API") or DEFAULT_API).rstrip("/")
        if not self.token:
            raise RuntimeError("GITHUB_TOKEN が未設定です（.env に repo スコープの PAT を設定してください）。")
        if "/" not in self.repo:
            raise RuntimeError("GITHUB_REPO が未設定/不正です（owner/name 形式で指定してください）。")
        self.owner = self.repo.split("/", 1)[0]
        self._s = requests.Session()
        self._s.headers.update(
            {
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            }
        )

    # --- low-level helpers ---------------------------------------------------
    def _url(self, path: str) -> str:
        return f"{self.api}/repos/{self.repo}{path}"

    @staticmethod
    def _msg(resp: requests.Response) -> str:
        try:
            return resp.json().get("message", "") or resp.text[:200]
        except ValueError:
            return resp.text[:200]

    def _req(self, method: str, path: str, **kw) -> dict:
        r = self._s.request(method, self._url(path), timeout=_TIMEOUT, **kw)
        if r.status_code >= 400:
            raise RuntimeError(f"GitHub API {method} {path} -> {r.status_code}: {self._msg(r)}")
        return r.json() if r.text else {}

    def _default_branch(self) -> str:
        # 最初のrepoアクセス。404/403はトークンの権限問題が大半なので分かりやすく案内する。
        r = self._s.get(self._url(""), timeout=_TIMEOUT)
        if r.status_code in (403, 404):
            raise RuntimeError(
                f"リポジトリ {self.repo} にアクセスできません（{r.status_code}）。PATの権限を確認してください — "
                "fine-grained: Resource owner=該当org / 対象repoを選択 / Contents=Read and write・Pull requests=Read and write / org承認済み。"
                "classic: repo スコープ ＋（SSO必須orgなら）トークンのSSO認可。"
                "（GITHUB_REPO の owner/name 表記ズレも確認）"
            )
        if r.status_code >= 400:
            raise RuntimeError(f"GitHub API GET /repos/{self.repo} -> {r.status_code}: {self._msg(r)}")
        return r.json()["default_branch"]

    def _ref_sha(self, branch: str) -> str:
        return self._req("GET", f"/git/ref/heads/{branch}")["object"]["sha"]

    def _ensure_base(self, base: str) -> str:
        """base ブランチの先端SHAを返す。空リポジトリ(409)なら初期コミットで作る。"""
        r = self._s.get(self._url(f"/git/ref/heads/{base}"), timeout=_TIMEOUT)
        if r.status_code == 200:
            return r.json()["object"]["sha"]
        if r.status_code == 409:  # "Git Repository is empty" → base を初期化
            logger.info("空リポジトリのため %s を初期コミットで初期化します", base)
            self._bootstrap_initial_commit(base)
            return self._ref_sha(base)
        raise RuntimeError(f"GitHub API GET /git/ref/heads/{base} -> {r.status_code}: {self._msg(r)}")

    def _bootstrap_initial_commit(self, base: str) -> None:
        """空リポジトリに README を1つコミットして base ブランチを生成する。"""
        body = {
            "message": "chore: initialize repository",
            "content": base64.b64encode(_INIT_README.encode("utf-8")).decode("ascii"),
            "branch": base,
        }
        r = self._s.put(self._url("/contents/README.md"), json=body, timeout=_TIMEOUT)
        if r.status_code >= 400:
            raise RuntimeError(f"リポジトリ初期化に失敗: {r.status_code}: {self._msg(r)}")

    def _branch_exists(self, branch: str) -> bool:
        r = self._s.get(self._url(f"/git/ref/heads/{branch}"), timeout=_TIMEOUT)
        return r.status_code == 200

    def _unique_branch(self, base_name: str) -> str:
        """衝突しないブランチ名を決定論で選ぶ（base, base-2, base-3, ...）。"""
        name = base_name
        for i in range(2, 21):
            if not self._branch_exists(name):
                return name
            name = f"{base_name}-{i}"
        return name  # 出尽くしたらそのまま（作成側で衝突検知）

    def _create_branch(self, branch: str, base_sha: str) -> None:
        self._req("POST", "/git/refs", json={"ref": f"refs/heads/{branch}", "sha": base_sha})

    def _put_file(self, path: str, content: str, branch: str, message: str) -> None:
        body = {
            "message": message,
            "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
            "branch": branch,
        }
        r = self._s.put(self._url(f"/contents/{path}"), json=body, timeout=_TIMEOUT)
        if r.status_code == 422:  # 既存ファイル → sha を付けて更新で再試行
            g = self._s.get(self._url(f"/contents/{path}"), params={"ref": branch}, timeout=_TIMEOUT)
            if g.status_code == 200:
                body["sha"] = g.json().get("sha")
                r = self._s.put(self._url(f"/contents/{path}"), json=body, timeout=_TIMEOUT)
        if r.status_code >= 400:
            raise RuntimeError(f"ファイルコミット失敗 {path}: {r.status_code} {self._msg(r)}")

    def _open_pr(self, branch: str, base: str, title: str, body: str) -> str:
        r = self._s.post(
            self._url("/pulls"),
            json={"title": title, "head": branch, "base": base, "body": body},
            timeout=_TIMEOUT,
        )
        if r.status_code < 400:
            return r.json()["html_url"]
        # 既に同 head→base の open PR があれば再利用する
        ex = self._s.get(
            self._url("/pulls"),
            params={"head": f"{self.owner}:{branch}", "base": base, "state": "open"},
            timeout=_TIMEOUT,
        )
        if ex.status_code == 200 and ex.json():
            return ex.json()[0]["html_url"]
        raise RuntimeError(f"PR作成失敗: {r.status_code}: {self._msg(r)}")

    # --- public --------------------------------------------------------------
    def publish_app(
        self,
        app_name: str,
        files: list[GeneratedFile],
        *,
        summary: str = "",
    ) -> PublishResponse:
        base = self._default_branch()
        base_sha = self._ensure_base(base)  # 空リポジトリなら初期コミットで base を作る
        branch = self._unique_branch(f"feat/{slug_branch(app_name)}")
        self._create_branch(branch, base_sha)

        committed: list[str] = []
        for f in files:
            self._put_file(f.path, f.content, branch, f"feat: add {f.path}")
            committed.append(f.path)

        pr_url = self._open_pr(
            branch,
            base,
            f"feat: generate cFS app {app_name}",
            _pr_body(app_name, summary, committed),
        )
        return PublishResponse(
            ok=True,
            repo=self.repo,
            branch=branch,
            pr_url=pr_url,
            message=f"{len(committed)}ファイルを {branch} にコミットし、{base} 宛のPRを作成しました。",
            notes=committed,
        )


def _pr_body(app_name: str, summary: str, files: list[str]) -> str:
    lines = [
        "AI駆動FSW開発プラットフォーム（体験版）が生成した cFS アプリです。",
        "",
        f"- **app**: `{app_name}`",
    ]
    if summary:
        lines.append(f"- **summary**: {summary}")
    lines += ["", "### 生成ファイル", *[f"- `{p}`" for p in files]]
    lines += ["", "> 骨格生成段階のため、ビルド/実行検証は後続Sprint（軽量検証）で行います。"]
    return "\n".join(lines)
