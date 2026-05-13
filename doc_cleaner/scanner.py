from __future__ import annotations
import hashlib
import mimetypes
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

SKIP_DIRS: frozenset[str] = frozenset({
    "node_modules", ".git", "Library", "Applications", "System",
    ".Trash", "__pycache__", ".venv", "venv", "env",
    "site-packages", ".tox", "dist", "build", "Caches",
})


@dataclass
class FileMetadata:
    original_path: Path
    relative_path: Path
    filename: str
    extension: str        # lowercase with dot, e.g. ".pdf"
    file_size: int        # bytes
    created_time: float | None
    modified_time: float
    mime_type: str
    file_hash: str        # SHA-256 hex digest


def scan_files(
    input_dir: Path,
    max_depth: int | None = None,
    include_hidden: bool = False,
    follow_symlinks: bool = False,
    max_files: int | None = None,
) -> Iterator[FileMetadata]:
    count = 0
    input_dir = input_dir.resolve()

    for root, dirs, files in os.walk(str(input_dir), followlinks=follow_symlinks):
        root_path = Path(root)
        depth = len(root_path.relative_to(input_dir).parts)

        if max_depth is not None and depth >= max_depth:
            dirs.clear()
            continue

        # Filter subdirs in-place (controls os.walk traversal)
        dirs[:] = sorted([
            d for d in dirs
            if (include_hidden or not d.startswith("."))
            and d not in SKIP_DIRS
        ])

        for filename in sorted(files):
            if max_files is not None and count >= max_files:
                return
            if not include_hidden and filename.startswith("."):
                continue

            file_path = root_path / filename
            if not follow_symlinks and file_path.is_symlink():
                continue

            try:
                meta = _build_metadata(file_path, input_dir)
                yield meta
                count += 1
            except (PermissionError, OSError):
                continue


def _build_metadata(file_path: Path, base_dir: Path) -> FileMetadata:
    stat = file_path.stat()
    return FileMetadata(
        original_path=file_path.resolve(),
        relative_path=file_path.relative_to(base_dir),
        filename=file_path.name,
        extension=file_path.suffix.lower(),
        file_size=stat.st_size,
        created_time=getattr(stat, "st_birthtime", None),
        modified_time=stat.st_mtime,
        mime_type=_detect_mime(file_path),
        file_hash=_sha256(file_path),
    )


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _detect_mime(path: Path) -> str:
    try:
        import magic
        return magic.from_file(str(path), mime=True)
    except (ImportError, Exception):
        guessed, _ = mimetypes.guess_type(path.name)
        return guessed or "application/octet-stream"
