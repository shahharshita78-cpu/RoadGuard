"""
Prediction service and persistence layer for RoadGuard Predictive Analytics.
Handles SQLite schema, prediction record persistence, validation, and inference explainability.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

import numpy as np
import pandas as pd
import xgboost as xgb

from .model import load_model_artifacts, train_and_save_pipeline, VERSION
from .features import prepare_single_inference_features, FEATURE_COLS
from .data import load_raw_dataset

# DB path same as inspection service
DB_PATH = Path(__file__).parents[4] / "detections.db"

# Risk category thresholds
RISK_THRESHOLD_CRITICAL = 0.75
RISK_THRESHOLD_HIGH = 0.50
RISK_THRESHOLD_MEDIUM = 0.25


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_prediction_schema() -> None:
    """Create the road_predictions table if it does not exist."""
    conn = _get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS road_predictions (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            prediction_id           TEXT UNIQUE NOT NULL,
            timestamp               TEXT NOT NULL,
            road_segment_id         TEXT NOT NULL,
            model_version           TEXT NOT NULL,
            risk_probability        REAL NOT NULL,
            risk_category           TEXT NOT NULL,
            predicted_future_health REAL NOT NULL,
            top_factors             TEXT NOT NULL,
            feature_snapshot        TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def save_prediction(record: dict) -> dict:
    """Insert a new prediction record into the SQLite database."""
    ensure_prediction_schema()
    conn = _get_connection()
    conn.execute(
        """
        INSERT INTO road_predictions (
            prediction_id, timestamp, road_segment_id, model_version,
            risk_probability, risk_category, predicted_future_health,
            top_factors, feature_snapshot
        ) VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (
            record["prediction_id"],
            record["timestamp"],
            record["road_segment_id"],
            record["model_version"],
            record["risk_probability"],
            record["risk_category"],
            record["predicted_future_health"],
            json.dumps(record["top_factors"]),
            json.dumps(record["feature_snapshot"]),
        ),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM road_predictions WHERE prediction_id = ?",
        (record["prediction_id"],),
    ).fetchone()
    conn.close()
    return _deserialise_prediction(dict(row))


def get_all_predictions() -> List[dict]:
    """Return all prediction records, newest first."""
    ensure_prediction_schema()
    conn = _get_connection()
    rows = conn.execute(
        "SELECT * FROM road_predictions ORDER BY timestamp DESC"
    ).fetchall()
    conn.close()
    return [_deserialise_prediction(dict(r)) for r in rows]


def get_predictions_by_road(road_segment_id: str) -> List[dict]:
    """Return all predictions for a specific road segment, newest first."""
    ensure_prediction_schema()
    conn = _get_connection()
    rows = conn.execute(
        "SELECT * FROM road_predictions WHERE road_segment_id = ? ORDER BY timestamp DESC",
        (road_segment_id,),
    ).fetchall()
    conn.close()
    return [_deserialise_prediction(dict(r)) for r in rows]


def _deserialise_prediction(row: dict) -> dict:
    """Parse JSON blob columns back to Python objects."""
    for key in ("top_factors", "feature_snapshot"):
        raw = row.get(key)
        if isinstance(raw, str):
            try:
                row[key] = json.loads(raw)
            except (ValueError, TypeError):
                row[key] = {} if key == "feature_snapshot" else []
    return row


def assign_risk_category(prob: float) -> str:
    """Categorise deterioration probability based on configurable thresholds."""
    if prob >= RISK_THRESHOLD_CRITICAL:
        return "CRITICAL"
    if prob >= RISK_THRESHOLD_HIGH:
        return "HIGH"
    if prob >= RISK_THRESHOLD_MEDIUM:
        return "MEDIUM"
    return "LOW"


def explain_prediction(clf: xgb.XGBClassifier, X: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Generate local explainability indicators using XGBoost native tree-contributions.
    Maps log-odds margin contributions to human-readable explanations.
    """
    booster = clf.get_booster()
    dmat = xgb.DMatrix(X)
    # predict with pred_contribs=True returns contributions for each feature + bias term
    contribs = booster.predict(dmat, pred_contribs=True)[0]
    
    factors = []
    
    # Human readable feature mapping labels
    feature_labels = {
        "road_health_score": "Current road health decline",
        "severity_score": "Current severity level",
        "priority_score": "Existing priority score",
        "detection_count": "Number of detected defects",
        "avg_confidence": "Detection confidence rate",
        "max_severity_score": "Extreme single-defect severity",
        "damage_frame_pct": "High frequency of damage frames",
        "unique_detections": "Deduplicated unique defect counts",
        "days_since_previous_inspection": "Prolonged period between inspections",
        "previous_road_health_score": "Historical road health baseline",
        "deterioration_rate": "Accelerated rate of health degradation",
        "number_of_previous_inspections": "Total inspection historical frequency",
        "damage_count_D00": "Longitudinal cracks presence",
        "damage_count_D10": "Transverse cracks presence",
        "damage_count_D20": "Alligator cracks presence",
        "damage_count_D40": "Severe potholes presence",
    }

    for i, col in enumerate(X.columns):
        contrib_val = float(contribs[i])
        # Only report features that had a non-trivial impact
        if abs(contrib_val) > 0.005:
            direction = "increased" if contrib_val > 0 else "decreased"
            label = feature_labels.get(col, col.replace("_", " ").capitalize())
            factors.append({
                "feature": col,
                "label": label,
                "contribution": round(contrib_val, 4),
                "direction": direction,
                "importance": round(abs(contrib_val), 4)
            })

    # Sort factors by absolute impact descending
    factors = sorted(factors, key=lambda f: f["importance"], reverse=True)
    return factors


def run_prediction_pipeline(payload: dict) -> dict:
    """
    Inferences the deterioration models for a given feature payload.
    Validates inputs, runs class/reg models, constructs explainability metrics,
    and returns a structured prediction response.
    """
    # 1. Load artifacts
    clf, reg, meta = load_model_artifacts()
    
    if clf is None or reg is None or meta is None:
        # Auto-train prototype if no model exists
        df_raw = load_raw_dataset()
        meta = train_and_save_pipeline(df_raw, high_priority_threshold=65, is_synthetic=True)
        clf, reg, meta = load_model_artifacts()

    # 2. Check for NaN or inf values in input
    for k, v in payload.items():
        if isinstance(v, (int, float)):
            if np.isnan(v) or np.isinf(v):
                raise ValueError(f"Invalid numeric input for '{k}': NaN or Inf not allowed.")

    # 3. Format input to DataFrame
    X_infer = prepare_single_inference_features(payload)

    # 4. Predict probability and future health
    prob = float(clf.predict_proba(X_infer)[0, 1])
    pred_health = float(reg.predict(X_infer)[0])
    
    # Clamp future health between 0 and 100
    pred_health = max(0.0, min(100.0, pred_health))

    # 5. Risk Category & Explainability
    risk_cat = assign_risk_category(prob)
    factors = explain_prediction(clf, X_infer)

    # Determine recommended inspection urgency based on risk category
    urgency_map = {
        "CRITICAL": "Immediate inspection required within 7 days",
        "HIGH": "Schedule follow-up inspection within 30 days",
        "MEDIUM": "Routine inspection within 90 days",
        "LOW": "Standard annual inspection schedule"
    }

    # Snapshot of features used for inference
    feature_snapshot = X_infer.iloc[0].to_dict()

    prediction_result = {
        "prediction_id": str(uuid.uuid4()),
        "timestamp": datetime.utcnow().isoformat(),
        "road_segment_id": payload.get("road_segment_id", "UNKNOWN"),
        "model_version": meta.get("version", VERSION),
        "risk_probability": round(prob, 4),
        "risk_category": risk_cat,
        "predicted_future_health": round(pred_health, 1),
        "top_factors": factors,
        "urgency_recommendation": urgency_map.get(risk_cat, "Standard schedule"),
        "feature_snapshot": feature_snapshot
    }

    return prediction_result
