"""
Predictive Analytics API endpoints for RoadGuard (Phase 12).
Exposes endpoints for deterioration prediction, model training, and aggregate summaries.
"""
from __future__ import annotations

from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from ..services.prediction import (
    run_prediction_pipeline,
    save_prediction,
    get_all_predictions,
    get_predictions_by_road,
    load_model_artifacts,
    train_and_save_pipeline,
    load_raw_dataset
)

router = APIRouter()


class DeteriorationRequest(BaseModel):
    road_segment_id: str = Field(..., description="Unique road segment identifier")
    road_health_score: float = Field(..., ge=0.0, le=100.0, description="Current Road Health Index")
    severity_score: float = Field(..., ge=0.0, le=100.0, description="Current Severity score")
    priority_score: float = Field(..., ge=0.0, le=100.0, description="Current Maintenance Priority score")
    detection_count: int = Field(..., ge=0, description="Current defect count")
    avg_confidence: float = Field(0.0, ge=0.0, le=1.0, description="Average confidence score")
    max_severity_score: float = Field(0.0, ge=0.0, le=100.0, description="Maximum single defect severity score")
    damage_frame_pct: float = Field(0.0, ge=0.0, le=100.0, description="Percentage of frames with damage (video only)")
    unique_detections: int = Field(0, ge=0, description="Unique deduplicated defect count (video only)")
    days_since_previous_inspection: float = Field(0.0, ge=0.0, description="Days elapsed since previous inspection")
    previous_road_health_score: float = Field(100.0, ge=0.0, le=100.0, description="Road health index in previous inspection")
    deterioration_rate: float = Field(0.0, description="Decline in road health per day since last inspection")
    number_of_previous_inspections: int = Field(0, ge=0, description="Total count of historical inspections")
    damage_class_counts: Dict[str, int] = Field(default_factory=dict, description="Counts of D00, D10, D20, D40 damage types")


@router.post(
    "/predictions/deterioration",
    tags=["Predictions"],
    summary="Predict deterioration risk probability for a road segment",
)
def predict_deterioration(req: DeteriorationRequest) -> Dict[str, Any]:
    """
    Compute deterioration probability, risk category, and contributing factors.
    Stores the prediction result in the database.
    """
    payload = req.model_dump()
    try:
        result = run_prediction_pipeline(payload)
        saved = save_prediction(result)
        return saved
    except ValueError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(err)
        )
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Inference failed: {err}"
        )


@router.get(
    "/predictions/model",
    tags=["Predictions"],
    summary="Retrieve deterioration model metadata and metrics",
)
def get_model_info() -> Dict[str, Any]:
    """
    Return training version, date, sample counts, feature details,
    and validation performance metrics.
    """
    _, _, meta = load_model_artifacts()
    if meta is None:
        try:
            # Auto-train default model if none exists
            df_raw = load_raw_dataset()
            meta = train_and_save_pipeline(df_raw, high_priority_threshold=65, is_synthetic=True)
        except Exception as err:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Model not trained and auto-training failed: {err}"
            )
    return meta


@router.get(
    "/predictions/risk-summary",
    tags=["Predictions"],
    summary="Retrieve aggregate risk summaries and evaluations",
)
def get_risk_summary() -> Dict[str, Any]:
    """
    Return summary statistics based on the latest prediction for each road segment.
    """
    all_preds = get_all_predictions()
    if not all_preds:
        # Load synthetic raw dataset to pre-populate predictions for overview
        try:
            df_raw = load_raw_dataset()
            # Feed some segments into pipeline to seed database if empty
            unique_segments = df_raw["road_segment_id"].unique()[:10]
            for segment in unique_segments:
                seg_data = df_raw[df_raw["road_segment_id"] == segment].iloc[-1]
                counts = {}
                import json
                try:
                    counts = json.loads(seg_data["damage_class_counts"])
                except Exception:
                    pass
                payload = {
                    "road_segment_id": segment,
                    "road_health_score": float(seg_data["road_health_score"]),
                    "severity_score": float(seg_data["severity_score"]),
                    "priority_score": float(seg_data["priority_score"]),
                    "detection_count": int(seg_data["detection_count"]),
                    "avg_confidence": float(seg_data["avg_confidence"]),
                    "max_severity_score": float(seg_data["max_severity_score"]),
                    "damage_frame_pct": float(seg_data["damage_frame_pct"]),
                    "unique_detections": int(seg_data["unique_detections"]),
                    "days_since_previous_inspection": float(seg_data["days_since_previous_inspection"]),
                    "previous_road_health_score": float(seg_data["previous_road_health_score"]),
                    "deterioration_rate": float(seg_data["deterioration_rate"]),
                    "number_of_previous_inspections": int(seg_data["number_of_previous_inspections"]),
                    "damage_class_counts": counts
                }
                res = run_prediction_pipeline(payload)
                save_prediction(res)
            all_preds = get_all_predictions()
        except Exception:
            pass

    if not all_preds:
        return {
            "total_roads_evaluated": 0,
            "risk_counts": {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0},
            "avg_risk_probability": 0.0,
            "latest_predictions": []
        }

    # Group by segment to get the latest prediction for each
    latest_by_road: Dict[str, dict] = {}
    # Since get_all_predictions returns newest first, the first one seen per road is the latest
    for p in all_preds:
        road = p["road_segment_id"]
        if road not in latest_by_road:
            latest_by_road[road] = p

    latest_list = list(latest_by_road.values())
    total_roads = len(latest_list)

    risk_counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
    total_prob = 0.0

    for p in latest_list:
        cat = p["risk_category"]
        risk_counts[cat] = risk_counts.get(cat, 0) + 1
        total_prob += p["risk_probability"]

    avg_prob = total_prob / total_roads if total_roads > 0 else 0.0

    return {
        "total_roads_evaluated": total_roads,
        "risk_counts": risk_counts,
        "avg_risk_probability": round(avg_prob, 4),
        "latest_predictions": latest_list
    }


@router.post(
    "/predictions/train",
    tags=["Predictions"],
    summary="Retrain the deterioration model",
)
def train_model(high_priority_threshold: int = 65) -> Dict[str, Any]:
    """
    Retrain the classifier and regressor using the longitudinal training data.
    """
    try:
        df_raw = load_raw_dataset()
        meta = train_and_save_pipeline(
            df_raw,
            high_priority_threshold=high_priority_threshold,
            is_synthetic=True
        )
        return {
            "status": "success",
            "message": "Model retrained successfully",
            "metadata": meta
        }
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Training failed: {err}"
        )
