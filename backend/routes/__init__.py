from fastapi import APIRouter

from backend.routes.data import router as data_router
from backend.routes.health import router as health_router
from backend.routes.insights import router as insights_router
from backend.routes.products import router as products_router
from backend.routes.receipts import router as receipts_router
from backend.routes.settings import router as settings_router
from backend.routes.spending import router as spending_router

router = APIRouter(prefix="/api")
router.include_router(health_router)
router.include_router(receipts_router)
router.include_router(products_router)
router.include_router(insights_router)
router.include_router(spending_router)
router.include_router(settings_router)
router.include_router(data_router)
