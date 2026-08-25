"""
Maintenance priority API endpoint.

POST /api/maintenance/priority  — compute priority for an arbitrary set of inputs
GET  /api/maintenance/queue     — ranked maintenance queue from stored inspections
"""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..services import optimizer, inspection as inspection_svc

router = APIRouter()


class PriorityRequest(BaseModel):
    severity_score: int = Field(..., ge=0, le=100)
    road_health_score: int = Field(..., ge=0, le=100)
    detection_count: int = Field(..., ge=0)


@router.post(
    "/maintenance/priority",
    tags=["Maintenance"],
    summary="Compute maintenance priority from explicit inputs",
)
def compute_priority(req: PriorityRequest) -> Dict[str, Any]:
    """
    Return maintenance priority for the supplied severity, health, and detection count.
    Useful for what-if analysis without a new image upload.
    """
    return optimizer.compute_maintenance_priority(
        req.severity_score,
        req.road_health_score,
        req.detection_count,
    )


@router.get(
    "/maintenance/queue",
    tags=["Maintenance"],
    summary="Ranked maintenance queue from all stored inspections",
)
def maintenance_queue() -> List[Dict[str, Any]]:
    """
    Return all inspections ranked by priority_score descending.
    Each entry shows location, damage summary, and priority metadata.
    """
    records = inspection_svc.get_all_inspections()
    queue = sorted(records, key=lambda r: r.get("priority_score", 0), reverse=True)

    return [
        {
            "inspection_id": r["inspection_id"],
            "timestamp": r["timestamp"],
            "image_name": r["image_name"],
            "latitude": r["latitude"],
            "longitude": r["longitude"],
            "address": r["address"],
            "damage_classes": r["damage_classes"],
            "detection_count": r["detection_count"],
            "severity": r["severity"],
            "severity_score": r["severity_score"],
            "road_condition": r["road_condition"],
            "road_health_score": r["road_health_score"],
            "priority": r["priority"],
            "priority_score": r["priority_score"],
        }
        for r in queue
    ]
