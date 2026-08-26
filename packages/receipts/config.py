"""Receipt tracker settings — data lives under the unified Finance App data dir."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.paths import get_receipts_db_path, get_receipts_images_dir, get_data_dir, repo_root
from app.settings_store import load_settings

ROOT_DIR = repo_root()
DATA_DIR = get_data_dir()
RECEIPTS_DIR = get_receipts_images_dir()
DB_PATH = Path(os.environ["RECEIPT_TRACKER_DB"]) if "RECEIPT_TRACKER_DB" in os.environ else get_receipts_db_path()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_DIR / ".env", extra="ignore")

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        stored = load_settings()
        if not self.openai_api_key and stored.get("openai_api_key"):
            self.openai_api_key = stored["openai_api_key"]
        if stored.get("openai_model"):
            self.openai_model = stored["openai_model"]


settings = Settings()
