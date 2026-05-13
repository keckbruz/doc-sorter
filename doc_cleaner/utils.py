from __future__ import annotations
import re
import shutil
import hashlib
from pathlib import Path

FORBIDDEN_CHARS = re.compile(r'[:/\\*?"<>|]')
MULTI_SPACE = re.compile(r' {2,}')
MAX_STEM_LEN = 196  # leaves room for " (2)" collision suffix


def sanitize_filename(
    date: str | None,
    sender: str | None,
    document_type: str | None,
    original_stem: str,
    extension: str,
) -> str:
    parts: list[str] = []

    parts.append(date if date else "undated")

    if sender:
        clean = FORBIDDEN_CHARS.sub("", sender).strip()
        clean = MULTI_SPACE.sub(" ", clean)
        if clean:
            parts.append(clean)

    type_part = document_type if document_type else original_stem
    clean_type = FORBIDDEN_CHARS.sub("", type_part).strip()
    clean_type = MULTI_SPACE.sub(" ", clean_type)
    if clean_type:
        parts.append(clean_type)

    stem = " - ".join(parts)
    stem = stem[:200 - len(extension)]
    return stem + extension


def safe_target_path(
    output_root: Path,
    category: str,
    subcategory: str | None,
    filename: str,
) -> Path:
    # Reject any path component that is or contains ".." before sanitization
    for segment in [category, subcategory, filename]:
        if segment is None:
            continue
        # Split on both posix and windows separators to catch traversal attempts
        for part in re.split(r"[/\\]", segment):
            if part == "..":
                raise ValueError(
                    f"Path traversal detected: '..' component found in '{segment}'"
                )

    # Strip forbidden chars from model-supplied category/subcategory
    safe_cat = FORBIDDEN_CHARS.sub("", category).strip()
    safe_sub = FORBIDDEN_CHARS.sub("", subcategory).strip() if subcategory else None

    if safe_sub:
        target = output_root / safe_cat / safe_sub / filename
    else:
        target = output_root / safe_cat / filename

    # Secondary path traversal guard: resolved path must stay under output_root
    try:
        target.resolve().relative_to(output_root.resolve())
    except ValueError:
        raise ValueError(
            f"Path traversal detected: computed path {target} is not under {output_root}"
        )
    return target


def safe_move(src: Path, dst: Path) -> Path:
    """Move src to dst. Never overwrites. Returns the actual destination path used."""
    if not src.exists():
        raise FileNotFoundError(f"Source not found: {src}")

    actual = _collision_safe(dst)
    actual.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(actual))
    return actual


def _collision_safe(dst: Path) -> Path:
    if not dst.exists():
        return dst
    stem = dst.stem
    suffix = dst.suffix
    parent = dst.parent
    for i in range(2, 100):
        candidate = parent / f"{stem} ({i}){suffix}"
        if not candidate.exists():
            return candidate
    # Last resort: short hash
    h = hashlib.md5(str(dst).encode()).hexdigest()[:6]
    fallback = parent / f"{stem}-{h}{suffix}"
    if fallback.exists():
        raise FileExistsError(f"Cannot find a safe target path for {dst}")
    return fallback
