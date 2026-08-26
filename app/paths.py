"""Application data directories and path helpers."""

from __future__ import annotations

import os
import sys
from pathlib import Path


APP_NAME = "FinanceApp"


def _default_data_dir() -> Path:
    override = os.environ.get("FINANCE_APP_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    return Path.home() / ".finance-app"


def get_data_dir() -> Path:
    path = _default_data_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_bank_dir() -> Path:
    path = get_data_dir() / "bank"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_receipts_dir() -> Path:
    path = get_data_dir() / "receipts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_receipts_db_path() -> Path:
    return get_data_dir() / "receipts.db"


def get_receipts_images_dir() -> Path:
    path = get_receipts_dir() / "images"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_settings_path() -> Path:
    return get_data_dir() / "settings.json"


def get_web_dir() -> Path:
    """Locate bundled web assets (dev checkout or PyInstaller bundle)."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        bundled = Path(sys._MEIPASS) / "web"
        if bundled.exists():
            return bundled
    return Path(__file__).resolve().parent.parent / "web"


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent
