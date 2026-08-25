"""
Analytics API endpoint.

GET /api/analytics/summary — aggregate statistics across all inspections
"""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter

from ..services import inspection as inspection_svc

router = APIRouter()


@router.get(
    "/analytics/summary",
    tags=["Analytics"],
    summary="Aggregate statistics across all stored inspections",
)
def analytics_summary() -> Dict[str, Any]:
    """
    Return aggregate KPIs computed from all stored inspection records.

    Metrics:
        total_inspections: int
        total_detections: int
        critical_inspections: int   (road_health_score < 30)
        avg_road_health: float
        avg_severity_score: float
        class_distribution: {class: count}
        priority_distribution: {priority: count}
    """
    import json

    records = inspection_svc.get_all_inspections()

    if not records:
        return {
            "total_inspections": 0,
            "total_detections": 0,
            "critical_inspections": 0,
            "avg_road_health": 100.0,
            "avg_severity_score": 0.0,
            "class_distribution": {},
            "priority_distribution": {},
        }

    total_inspections = len(records)
    total_detections = sum(r["detection_count"] for r in records)
    critical_inspections = sum(1 for r in records if r["road_health_score"] < 30)
    avg_health = round(sum(r["road_health_score"] for r in records) / total_inspections, 1)
    avg_severity = round(sum(r["severity_score"] for r in records) / total_inspections, 1)

    class_dist: Dict[str, int] = {}
    priority_dist: Dict[str, int] = {}

    for r in records:
        try:
            classes: List[str] = json.loads(r.get("damage_classes") or "[]")
        except (ValueError, TypeError):
            classes = []
        for cls in classes:
            class_dist[cls] = class_dist.get(cls, 0) + 1

        prio = r.get("priority", "Unknown")
        priority_dist[prio] = priority_dist.get(prio, 0) + 1

    return {
        "total_inspections": total_inspections,
        "total_detections": total_detections,
        "critical_inspections": critical_inspections,
        "avg_road_health": avg_health,
        "avg_severity_score": avg_severity,
        "class_distribution": class_dist,
        "priority_distribution": priority_dist,
    }
