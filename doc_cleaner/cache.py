from __future__ import annotations
import hashlib
from pathlib import Path
from typing import Optional
from doc_cleaner.classifier.schema import ClassificationResult
from doc_cleaner.classifier.prompts import PROMPT_VERSION


class ResultCache:
    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        cache_dir.mkdir(parents=True, exist_ok=True)

    def _key(self, file_hash: str, model: str, ocr: bool) -> str:
        raw = f"{file_hash}:{model}:{PROMPT_VERSION}:ocr={ocr}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    def _path(self, key: str) -> Path:
        return self.cache_dir / f"{key}.json"

    def get(self, file_hash: str, model: str, ocr: bool = False) -> Optional[ClassificationResult]:
        path = self._path(self._key(file_hash, model, ocr))
        if not path.exists():
            return None
        try:
            return ClassificationResult.model_validate_json(path.read_text())
        except Exception:
            return None

    def set(self, file_hash: str, model: str, result: ClassificationResult, ocr: bool = False) -> None:
        path = self._path(self._key(file_hash, model, ocr))
        path.write_text(result.model_dump_json())
