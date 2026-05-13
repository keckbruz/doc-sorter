from __future__ import annotations
from pathlib import Path

try:
    import yaml
except ImportError:
    raise ImportError("PyYAML required: pip install pyyaml")

REVIEW_CATEGORY = "Review"

# Dict[category_name -> list[subcategory_names]]
Taxonomy = dict[str, list[str]]


def load_taxonomy(path: Path) -> Taxonomy:
    if not path.exists():
        raise FileNotFoundError(f"Taxonomy file not found: {path}")
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    if not isinstance(raw, dict):
        raise ValueError(f"Taxonomy file must be a YAML mapping: {path}")
    # Normalize: values may be None (empty list in YAML) or a list
    return {k: (v or []) for k, v in raw.items()}


def is_valid_category(category: str, subcategory: str | None, taxonomy: Taxonomy) -> bool:
    if category not in taxonomy:
        return False
    if subcategory is None:
        return True
    subs = taxonomy[category]
    return not subs or subcategory in subs


def normalize_category(
    category: str, subcategory: str | None, taxonomy: Taxonomy
) -> tuple[str, str | None]:
    """Return (category, subcategory) forced to valid values, or Review if invalid."""
    if not is_valid_category(category, subcategory, taxonomy):
        return REVIEW_CATEGORY, None
    return category, subcategory
