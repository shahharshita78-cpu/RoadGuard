"""
Maintenance Optimization API Endpoints (Phase 13).

POST /api/maintenance/optimize             — Perform Knapsack optimization
GET  /api/maintenance/optimization/latest  — Fetch the most recent run details
"""
from __future__ import annotations

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from ..services.maintenance_optimizer import (
    optimize_maintenance_plan,
    save_optimization,
    get_latest_optimization
)
from ..services.prediction import get_all_predictions
from ..services.inspection import get_all_inspections

router = APIRouter()


class SegmentCandidate(BaseModel):
    road_segment_id: str = Field(..., description="Unique road segment identifier")
    road_health_score: float = Field(..., ge=0.0, le=100.0)
    severity_score: float = Field(default=0.0, ge=0.0, le=100.0)
    priority_score: float = Field(default=0.0, ge=0.0, le=100.0)
    detection_count: int = Field(default=0, ge=0)
    avg_confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    damage_class_counts: Dict[str, int] = Field(default_factory=dict)
    deterioration_risk: Optional[float] = Field(None, ge=0.0, le=1.0, description="Phase 12 deterioration risk probability")
    predicted_future_health: Optional[float] = Field(None, ge=0.0, le=100.0, description="Phase 12 predicted future health index")


class OptimizationRequest(BaseModel):
    budget: float = Field(..., gt=0.0, description="Total available maintenance budget")
    road_segments: Optional[List[SegmentCandidate]] = Field(
        None,
        description="Optional explicit list of candidate road segments. If omitted, candidates will be sourced from SQLite predictions/inspections database."
    )


def _source_candidates_from_db() -> List[Dict[str, Any]]:
    """
    Source repair candidates from existing SQLite tables.
    Prioritizes Phase 12 prediction records, falling back to inspections where needed.
    """
    candidates = []
    
    # 1. Query Phase 12 predictions
    preds = get_all_predictions()
    
    if preds:
        # Group by segment ID to get the latest prediction for each segment
        latest_preds = {}
        for p in preds:
            seg_id = p["road_segment_id"]
            if seg_id not in latest_preds:
                latest_preds[seg_id] = p
                
        for seg_id, p in latest_preds.items():
            feat = p["feature_snapshot"]
            
            # Map numeric features back from the feature snapshot
            damage_counts = {
                "D00": int(feat.get("damage_count_D00", 0)),
                "D10": int(feat.get("damage_count_D10", 0)),
                "D20": int(feat.get("damage_count_D20", 0)),
                "D40": int(feat.get("damage_count_D40", 0)),
            }
            
            candidates.append({
                "road_segment_id": seg_id,
                "road_health_score": float(feat.get("road_health_score", 100.0)),
                "severity_score": float(feat.get("severity_score", 0.0)),
                "priority_score": float(feat.get("priority_score", 0.0)),
                "detection_count": int(feat.get("detection_count", 0)),
                "avg_confidence": float(feat.get("avg_confidence", 0.8)),
                "damage_class_counts": damage_counts,
                "deterioration_risk": float(p["risk_probability"]),
                "predicted_future_health": float(p["predicted_future_health"])
            })
            
    # 2. If no prediction entries exist, query standard inspections
    if not candidates:
        inspections = get_all_inspections()
        # Group by coordinates/address to represent segments
        seg_groups = {}
        for r in inspections:
            address = r.get("address") or r.get("image_name") or "Segment"
            if address not in seg_groups:
                seg_groups[address] = r
                
        for i, (addr, r) in enumerate(seg_groups.items(), 1):
            import json
            try:
                classes = json.loads(r.get("damage_classes") or "[]")
            except Exception:
                classes = []
            
            damage_counts = {c: 1 for c in classes}
            
            candidates.append({
                "road_segment_id": f"SEGMENT_{i:03d}_{addr[:12].replace('.', '').replace(' ', '_').upper()}",
                "road_health_score": float(r.get("road_health_score", 100.0)),
                "severity_score": float(r.get("severity_score", 0.0)),
                "priority_score": float(r.get("priority_score", 0.0)),
                "detection_count": int(r.get("detection_count", 0)),
                "avg_confidence": 0.8,
                "damage_class_counts": damage_counts,
                "deterioration_risk": None,
                "predicted_future_health": None
            })
            
    return candidates


@router.post(
    "/maintenance/optimize",
    tags=["Optimization"],
    summary="Compute optimal maintenance repair plan under budget constraints",
)
def optimize_plan(req: OptimizationRequest) -> Dict[str, Any]:
    """
    Executes Google OR-Tools optimization to select segments maximizing overall repair benefit.
    """
    if req.budget <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Maintenance budget must be greater than zero."
        )

    # Resolve candidates
    if req.road_segments is not None:
        candidates_raw = [s.model_dump() for s in req.road_segments]
    else:
        candidates_raw = _source_candidates_from_db()
        
    if not candidates_raw:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No candidate segments found in database and none provided in request payload."
        )

    try:
        result = optimize_maintenance_plan(candidates_raw, req.budget)
        saved = save_optimization(result)
        return saved
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(err)
        )
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Optimization failed: {err}"
        )


@router.get(
    "/maintenance/optimization/latest",
    tags=["Optimization"],
    summary="Retrieve the most recent maintenance optimization run result",
)
def get_latest() -> Dict[str, Any]:
    """
    Return the latest optimization plan from the database.
    """
    record = get_latest_optimization()
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No previous maintenance optimization runs found."
        )
    return record
