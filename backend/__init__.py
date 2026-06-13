"""fsw_ai_experience_platform backend パッケージ。"""
from pathlib import Path

from dotenv import load_dotenv

# リポジトリ直下の .env を自動読込（make backend 等で手動 source 不要にする）。
# override=False なので、シェルで export 済みの環境変数があればそちらが優先される。
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
