"""API v1 router — aggregates all sub-routers."""
from fastapi import APIRouter

from app.api.v1.scanner import router as scanner_router
from app.api.v1.risk import router as risk_router
from app.api.v1.wallet import router as wallet_router
from app.api.v1.realtime import router as realtime_router
from app.api.v1.graph import router as graph_router

router = APIRouter()

router.include_router(scanner_router)
router.include_router(risk_router)
router.include_router(wallet_router)
router.include_router(realtime_router)
router.include_router(graph_router)

__all__ = ["router"]
