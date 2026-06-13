"""キー不要の決定論モック GitHub provider。

PAT も実リポジトリも無しで、公開フロー（branch+PR）の一周を体験/検証するためのもの。
実際の API は叩かず、それらしい PR URL を決定論で返す。
"""
from __future__ import annotations

from .base import GitHubIntegration, slug_branch
from ..models import GeneratedFile, PublishResponse

MOCK_REPO = "mock-org/fsw-sandbox"


class MockGitHub(GitHubIntegration):
    name = "mock"

    def publish_app(
        self,
        app_name: str,
        files: list[GeneratedFile],
        *,
        summary: str = "",
    ) -> PublishResponse:
        branch = f"feat/{slug_branch(app_name)}"
        paths = [f.path for f in files]
        return PublishResponse(
            ok=True,
            repo=MOCK_REPO,
            branch=branch,
            pr_url=f"https://github.com/{MOCK_REPO}/pull/1",
            message=(
                f"（mock）{len(paths)}ファイルを {branch} にコミットし、main 宛のPRを作成した想定です。"
                "実GitHubに飛ばすには GITHUB_PROVIDER=github と GITHUB_TOKEN/GITHUB_REPO を設定してください。"
            ),
            notes=paths,
        )
