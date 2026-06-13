"""GitHub 連携の swappable 境界（抽象）。

mock / 実GitHub を同じインタフェースで差し替えられるようにする。フロー側は
get_github() で provider を得て publish_app() を呼ぶだけ（LLM境界と同じ作り）。
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import GeneratedFile, PublishResponse


def slug_branch(app_name: str) -> str:
    """app名から安全なブランチ名の末尾を作る（feat/<slug>）。"""
    s = "".join(c if (c.isalnum() or c in "-_.") else "-" for c in (app_name or "").strip().lower())
    return s.strip("-.") or "app"


class GitHubIntegration(ABC):
    name: str = "base"

    @abstractmethod
    def publish_app(
        self,
        app_name: str,
        files: list[GeneratedFile],
        *,
        summary: str = "",
    ) -> PublishResponse:
        """生成物を公開し、PR情報を返す。失敗は例外で送出（呼び出し側が握る）。"""
        raise NotImplementedError
