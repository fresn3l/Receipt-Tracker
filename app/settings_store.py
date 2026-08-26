"""Persisted app settings (OpenAI key, etc.)."""

from __future__ import annotations

import json
import os
from typing import Any

from app.paths import get_settings_path


def load_settings() -> dict[str, Any]:
    path = get_settings_path()
    if not path.exists():
        return {
            "openai_api_key": os.environ.get("OPENAI_API_KEY", ""),
            "openai_model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}
    data.setdefault("openai_api_key", os.environ.get("OPENAI_API_KEY", ""))
    data.setdefault("openai_model", os.environ.get("OPENAI_MODEL", "gpt-4o-mini"))
    return data


def save_settings(updates: dict[str, Any]) -> dict[str, Any]:
    current = load_settings()
    current.update({k: v for k, v in updates.items() if v is not None})
    path = get_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(current, indent=2), encoding="utf-8")
    if current.get("openai_api_key"):
        os.environ["OPENAI_API_KEY"] = str(current["openai_api_key"])
    if current.get("openai_model"):
        os.environ["OPENAI_MODEL"] = str(current["openai_model"])
    return current
