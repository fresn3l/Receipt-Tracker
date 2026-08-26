import re

STORE_ALIASES = {
    "walmart": "Walmart",
    "wal-mart": "Walmart",
    "target": "Target",
    "costco": "Costco",
    "kroger": "Kroger",
    "safeway": "Safeway",
    "trader joe": "Trader Joe's",
    "whole foods": "Whole Foods",
    "aldi": "Aldi",
    "publix": "Publix",
    "heb": "H-E-B",
    "sprouts": "Sprouts",
}


def normalize_store_name(name: str | None) -> str | None:
    if not name:
        return None
    cleaned = re.sub(r"\s+#?\d+\s*$", "", name.strip())
    cleaned = re.sub(r"\s+", " ", cleaned)
    lower = cleaned.lower()
    for key, canonical in STORE_ALIASES.items():
        if key in lower:
            return canonical
    return cleaned.title()
