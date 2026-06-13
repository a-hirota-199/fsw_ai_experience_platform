"""APIとフローで共有するデータモデル（Sprint 0）。"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class CommandItem(BaseModel):
    name: str
    summary: str = ""


class TelemetryItem(BaseModel):
    name: str
    rate_hz: float = 1
    fields: list[str] = Field(default_factory=list)


class StructuredRequirement(BaseModel):
    """要件構造化の成果物。Sprint 1 でコード生成の入力になる。"""

    app_name: str
    summary: str
    commands: list[CommandItem] = Field(default_factory=list)
    telemetry: list[TelemetryItem] = Field(default_factory=list)
    tables: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)


class StructureRequest(BaseModel):
    messages: list[ChatMessage]
    project_id: Optional[str] = None


class StructureResponse(BaseModel):
    mode: Literal["ask", "final"]
    message: str
    requirement: Optional[StructuredRequirement] = None


class GeneratedFile(BaseModel):
    path: str
    content: str


class GenerateRequest(BaseModel):
    requirement: StructuredRequirement


class GenerateResponse(BaseModel):
    app_name: str
    files: list[GeneratedFile] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class PublishRequest(BaseModel):
    """生成物を GitHub に公開（branch+PR）するための入力（Sprint 1 後半）。"""

    app_name: str
    files: list[GeneratedFile] = Field(default_factory=list)
    summary: str = ""


class PublishResponse(BaseModel):
    ok: bool = False
    repo: str = ""
    branch: str = ""
    pr_url: str = ""
    message: str = ""
    notes: list[str] = Field(default_factory=list)
