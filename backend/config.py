import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
RECEIPTS_DIR = DATA_DIR / "receipts"
DB_PATH = Path(os.environ["RECEIPT_TRACKER_DB"]) if "RECEIPT_TRACKER_DB" in os.environ else DATA_DIR / "receipts.db"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_DIR / ".env", extra="ignore")

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"


settings = Settings()
