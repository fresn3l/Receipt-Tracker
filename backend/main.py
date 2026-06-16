from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.database import Base, engine
from backend.migrations import run_migrations
from backend.routes import router

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="Receipt Tracker", version="0.1.0")
app.include_router(router)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    run_migrations()


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")
