"""
Feature engineering and target definition service for RoadGuard Predictive Analytics.
Prepares train/test feature matrices and targets from the longitudinal database.
"""
from __future__ import annotations

import json
import numpy as np
import pandas as pd
from typing import Tuple, List

# Define the expected feature columns
FEATURE_COLS = [
    "road_health_score",
    "severity_score",
    "priority_score",
    "detection_count",
    "avg_confidence",
    "max_severity_score",
    "damage_frame_pct",
    "unique_detections",
    "days_since_previous_inspection",
    "previous_road_health_score",
    "deterioration_rate",
    "number_of_previous_inspections",
    "damage_count_D00",
    "damage_count_D10",
    "damage_count_D20",
    "damage_count_D40",
]


def extract_features_and_targets(
    df: pd.DataFrame,
    high_priority_threshold: int = 65
) -> Tuple[pd.DataFrame, pd.Series, pd.Series, pd.DataFrame]:
    """
    Process raw longitudinal dataframe into feature matrices and targets.
    Filters out rows lacking a future observation (prediction targets).
    
    Returns:
        X: features DataFrame
        y_class: binary classification target (high priority in next period)
        y_reg: continuous regression target (future road health)
        df_clean: cleaned DataFrame containing metadata
    """
    df_clean = df.copy()

    # 1. Unpack damage class counts from JSON string
    def unpack_damage_counts(counts_json: str, cls: str) -> int:
        try:
            d = json.loads(counts_json)
            return int(d.get(cls, 0))
        except (ValueError, TypeError):
            return 0

    for cls in ["D00", "D10", "D20", "D40"]:
        col_name = f"damage_count_{cls}"
        df_clean[col_name] = df_clean["damage_class_counts"].apply(lambda x: unpack_damage_counts(x, cls))

    # 2. Drop rows with target leakage or missing targets
    # Rows with missing future observations represent the end of the history series
    valid_mask = df_clean["future_road_health"].notna() & df_clean["future_priority_score"].notna()
    df_train = df_clean[valid_mask].copy()

    if df_train.empty:
        raise ValueError("No valid records with targets found for training.")

    # 3. Create targets
    # Primary binary target: 1 if future priority score >= threshold, else 0
    y_class = (df_train["future_priority_score"] >= high_priority_threshold).astype(int)
    # Secondary continuous target: future road health score
    y_reg = df_train["future_road_health"].astype(float)

    # 4. Extract feature columns
    X = df_train[FEATURE_COLS].copy()

    # Fill NaNs/inf safely
    X.replace([np.inf, -np.inf], np.nan, inplace=True)
    X.fillna(0.0, inplace=True)

    return X, y_class, y_reg, df_train


def prepare_single_inference_features(payload: dict) -> pd.DataFrame:
    """
    Prepare a 1-row DataFrame for inference from a dictionary of raw features.
    Handles missing features gracefully by defaulting to 0.0.
    """
    record = {}
    
    # Extract regular features
    for col in FEATURE_COLS:
        if col.startswith("damage_count_"):
            cls = col.replace("damage_count_", "")
            # Look in payload's damage_class_counts dict or directly in payload
            cls_counts = payload.get("damage_class_counts", {})
            if isinstance(cls_counts, str):
                try:
                    cls_counts = json.loads(cls_counts)
                except Exception:
                    cls_counts = {}
            val = cls_counts.get(cls, payload.get(col, 0))
            record[col] = float(val)
        else:
            default_val = 100.0 if col == "previous_road_health_score" else 0.0
            record[col] = float(payload.get(col, default_val))

    X = pd.DataFrame([record])
    X.replace([np.inf, -np.inf], np.nan, inplace=True)
    X.fillna(0.0, inplace=True)
    return X
