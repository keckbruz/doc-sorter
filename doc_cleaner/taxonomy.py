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


def read_output_taxonomy(output_root: Path) -> Taxonomy:
    """Walk up to 2 levels of output_root dirs to build a taxonomy overlay."""
    result: Taxonomy = {}
    if not output_root.is_dir():
        return result
    for cat_dir in sorted(output_root.iterdir()):
        if not cat_dir.is_dir() or cat_dir.name.startswith("."):
            continue
        subs = [
            d.name for d in sorted(cat_dir.iterdir())
            if d.is_dir() and not d.name.startswith(".")
        ]
        result[cat_dir.name] = subs
    return result


def merge_taxonomies(base: Taxonomy, overlay: Taxonomy) -> Taxonomy:
    """Merge overlay into base. Adds new categories/subcategories; never removes."""
    merged = {k: list(v) for k, v in base.items()}
    for cat, subs in overlay.items():
        if cat in merged:
            existing = set(merged[cat])
            for sub in subs:
                if sub not in existing:
                    merged[cat].append(sub)
        else:
            merged[cat] = list(subs)
    return merged
