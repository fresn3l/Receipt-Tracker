"""Unified FastAPI application mounting banking + receipts + shell UI."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.migrate import migrate_legacy_data
from app.paths import get_data_dir, get_web_dir
from app.settings_store import load_settings, save_settings
from banking import service as bank_service
from banking.routes import router as bank_router
from receipts.config import settings as receipt_settings
from receipts.database import Base, engine
from receipts.migrations import run_migrations
from receipts.routes import router as receipts_router

logger = logging.getLogger(__name__)

WEB_DIR = get_web_dir()


def create_app() -> FastAPI:
    app = FastAPI(title="Finance App", version="0.1.0")
    app.include_router(bank_router)
    app.include_router(receipts_router)

    receipts_static = WEB_DIR / "receipts"
    banking_static = WEB_DIR / "banking"

    if receipts_static.exists():
        app.mount("/receipts/static", StaticFiles(directory=receipts_static), name="receipts-static")
    if banking_static.exists():
        app.mount("/banking/assets", StaticFiles(directory=banking_static), name="banking-assets")
    if WEB_DIR.exists():
        app.mount("/assets", StaticFiles(directory=WEB_DIR), name="shell-assets")

    @app.on_event("startup")
    def on_startup():
        migrate_legacy_data()
        bank_service.init_workflow()
        stored = load_settings()
        if stored.get("openai_api_key") and not receipt_settings.openai_api_key:
            receipt_settings.openai_api_key = stored["openai_api_key"]
        if not receipt_settings.openai_api_key:
            logger.warning("OPENAI_API_KEY is not set. Receipt parsing will fail until configured.")
        Base.metadata.create_all(bind=engine)
        run_migrations()

    @app.get("/")
    def index():
        return FileResponse(WEB_DIR / "index.html")

    @app.get("/banking")
    @app.get("/banking/")
    def banking_index():
        return FileResponse(WEB_DIR / "banking" / "index.html")

    @app.get("/receipts")
    @app.get("/receipts/")
    def receipts_index():
        return FileResponse(WEB_DIR / "receipts" / "index.html")

    @app.get("/api/app/settings")
    def get_app_settings():
        data = load_settings()
        key = data.get("openai_api_key") or ""
        return {
            "openai_api_key_set": bool(key),
            "openai_api_key_masked": ("*" * max(0, len(key) - 4) + key[-4:]) if key else "",
            "openai_model": data.get("openai_model", "gpt-4o-mini"),
            "data_dir": str(get_data_dir()),
        }

    @app.patch("/api/app/settings")
    def patch_app_settings(payload: dict):
        updates = {}
        if "openai_api_key" in payload:
            updates["openai_api_key"] = payload["openai_api_key"]
            receipt_settings.openai_api_key = payload["openai_api_key"] or ""
        if "openai_model" in payload:
            updates["openai_model"] = payload["openai_model"]
            receipt_settings.openai_model = payload["openai_model"]
        saved = save_settings(updates)
        return {
            "ok": True,
            "openai_api_key_set": bool(saved.get("openai_api_key")),
            "openai_model": saved.get("openai_model"),
        }

    @app.get("/api/app/dashboard")
    def dashboard_summary():
        from receipts.database import SessionLocal
        from receipts.spending import get_spending_summary

        bank_stats = bank_service.get_overall_stats()
        with SessionLocal() as db:
            grocery = get_spending_summary(db)
        return {"banking": bank_stats, "grocery": grocery}

    return app


app = create_app()
