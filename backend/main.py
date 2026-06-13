"""FastAPI エントリポイント（Sprint 0）。

起動例（リポジトリ直下）:
    uvicorn backend.main:app --reload --port 8000
"""
from __future__ import annotations

import os

from fastapi import FastAPI

from .flow.generate import generate_app
from .flow.structure import structure_step
from .models import GenerateRequest, GenerateResponse, StructureRequest, StructureResponse

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


@app.post("/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest) -> GenerateResponse:
    """構造化要件から cFS アプリのコードを生成する（Sprint 1）。"""
    try:
        return generate_app(req.requirement)
    except Exception as e:
        return GenerateResponse(app_name=req.requirement.app_name, files=[], notes=[f"生成エラー: {e}"])
