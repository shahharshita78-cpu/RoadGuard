"""
RoadGuard — Road Infrastructure Intelligence Platform
FastAPI application entry point.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import health, detection, inspections, analytics, maintenance
from .services.inspection import ensure_schema


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Initialise the SQLite database schema on application start."""
    ensure_schema()
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

# Allow the React frontend dev server to call the API during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
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
