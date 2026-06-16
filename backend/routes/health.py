from fastapi import APIRouter

from backend.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    return {
        "status": "ok",
        "openai_api_key_configured": bool(settings.openai_api_key),
    }
