"""
RoadGuard — Road Infrastructure Intelligence Platform
FastAPI application entry point.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import health, detection, inspections, analytics, maintenance, video, prediction, optimization
from .services.inspection import ensure_schema
from .services.video_inspection import ensure_video_schema
from .services.prediction import ensure_prediction_schema
from .services.maintenance_optimizer import ensure_optimization_schema


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Initialise the SQLite database schema on application start."""
    ensure_schema()
    ensure_video_schema()
    ensure_prediction_schema()
    ensure_optimization_schema()
    yield


app = FastAPI(
    title="RoadGuard API",
    description=(
        "Road Infrastructure Intelligence Platform — detect, score, and prioritise "
        "road surface damage using computer vision and analytical scoring."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

import os

# Parse allowed origins from environment variable or default to local development ports
cors_origins_raw = os.getenv(
    "CORS_ORIGINS", "http://localhost:5173,http://localhost:5174,http://localhost:3000"
)
allowed_origins = [origin.strip() for origin in cors_origins_raw.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Register routers under the /api prefix
app.include_router(health.router, prefix="/api")
app.include_router(detection.router, prefix="/api")
app.include_router(inspections.router, prefix="/api")
app.include_router(analytics.router, prefix="/api")
app.include_router(maintenance.router, prefix="/api")
app.include_router(video.router,       prefix="/api")
app.include_router(prediction.router,  prefix="/api")
app.include_router(optimization.router,prefix="/api")
