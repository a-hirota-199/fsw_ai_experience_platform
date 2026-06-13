"""FastAPI エントリポイント（Sprint 0）。

起動例（リポジトリ直下）:
    uvicorn backend.main:app --reload --port 8000
"""
from __future__ import annotations

import os

from fastapi import FastAPI

from .flow.structure import structure_step
from .models import StructureRequest, StructureResponse

app = FastAPI(title="fsw_ai_experience_platform backend", version="0.0.1")


@app.get("/health")
def health() -> dict:
    # llm_provider で現在の provider を確認できる（mock のままなら .env 未反映）
    return {"status": "ok", "llm_provider": os.getenv("LLM_PROVIDER", "mock")}


@app.post("/chat/structure", response_model=StructureResponse)
def chat_structure(req: StructureRequest) -> StructureResponse:
    """要件構造化フローを1ステップ進める（Sprint 0）。"""
    try:
        return structure_step(req.messages)
    except Exception as e:  # provider未設定・APIエラー等は体験を止めずチャットに返す
        return StructureResponse(mode="ask", message=f"LLM呼び出しエラー: {e}", requirement=None)
