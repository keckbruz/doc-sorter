# Classifier response schema
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, field_validator, Field


class ClassificationResult(BaseModel):
    category: str
    subcategory: Optional[str] = None
    document_date: Optional[str] = None
    sender: Optional[str] = None
    document_type: Optional[str] = None
    suggested_filename: str
    confidence: int = Field(default=0)
    reason: str = ""
    needs_review: bool = True

    @field_validator("confidence", mode="before")
    @classmethod
    def clamp_confidence(cls, v: object) -> int:
        try:
            return max(0, min(100, int(v)))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 0


class PlanRow(BaseModel):
    approved: bool = False
    status: str
    original_path: str
    target_path: str
    category: str
    subcategory: Optional[str] = None
    document_date: Optional[str] = None
    sender: Optional[str] = None
    document_type: Optional[str] = None
    suggested_filename: str
    confidence: int
    needs_review: bool
    reason: str
    file_size: int
    file_hash: str
    modified_time: str
    extractor: str
    model: str
    error: str = ""


class UndoEntry(BaseModel):
    original_path: str
    applied_path: str
    file_hash: str
    moved_at: str


class UndoManifest(BaseModel):
    created_at: str
    entries: list[UndoEntry]
