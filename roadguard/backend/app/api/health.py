"""Health check API endpoint."""
from __future__ import annotations

from fastapi import APIRouter

from ..models.schemas import HealthResponse
from ..services.detector import is_model_available

router = APIRouter()

VERSION = "1.0.0"


@router.get("/health", response_model=HealthResponse, tags=["System"])
def health_check() -> HealthResponse:
    """Return service liveness status and model readiness."""
    return HealthResponse(
        status="ok",
        model_loaded=is_model_available(),
        version=VERSION,
    )
