from fastapi import APIRouter

from receipts.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    return {
        "status": "ok",
        "openai_api_key_configured": bool(settings.openai_api_key),
    }
