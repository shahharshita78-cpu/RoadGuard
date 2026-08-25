"""
Inspections API endpoints.

GET  /api/inspections        — list all inspection records (newest first)
GET  /api/inspections/{id}   — retrieve a single inspection by UUID
"""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, HTTPException, status

from ..services import inspection as inspection_svc

router = APIRouter()


@router.get(
    "/inspections",
    tags=["Inspections"],
    summary="List all inspection records",
)
def list_inspections() -> List[dict]:
    """Return all stored inspection records ordered by timestamp descending."""
    return inspection_svc.get_all_inspections()


@router.get(
    "/inspections/{inspection_id}",
    tags=["Inspections"],
    summary="Retrieve a single inspection record",
)
def get_inspection(inspection_id: str) -> dict:
    """Return the inspection record with the given UUID."""
    record = inspection_svc.get_inspection_by_id(inspection_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inspection '{inspection_id}' not found.",
        )
    return record
