"""GitHub provider のファクトリ（LLM境界の get_provider と同じ作り）。

GITHUB_PROVIDER（既定: mock）で mock / 実GitHub を切り替える。実GitHubは依存を
利用時に解決し、未設定なら provider 内で分かりやすい RuntimeError を投げる。
"""
from __future__ import annotations

import os

from .base import GitHubIntegration
from .mock import MockGitHub


def get_github(name: str | None = None) -> GitHubIntegration:
    name = (name or os.getenv("GITHUB_PROVIDER", "mock")).lower()
    if name == "mock":
        return MockGitHub()
    if name in ("github", "real"):
        from .github import RealGitHub  # 利用時に解決

        return RealGitHub()
    raise ValueError(f"未知の GITHUB_PROVIDER: {name}（mock | github）")
