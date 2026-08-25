"""
Training, saving, and loading pipeline for RoadGuard Predictive Analytics.
Uses XGBoost Classifier and Regressor models trained on longitudinal datasets.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Tuple

import numpy as np
import pandas as pd
import xgboost as xgb

from .features import extract_features_and_targets, FEATURE_COLS
from .evaluation import evaluate_classifier, evaluate_regressor

# Model paths
SERVICE_DIR = Path(__file__).resolve().parent
ROOT_DIR = SERVICE_DIR.parents[4]
MODELS_DIR = ROOT_DIR / "models"

CLASSIFIER_PATH = MODELS_DIR / "road_deterioration_classifier.json"
REGRESSOR_PATH = MODELS_DIR / "road_deterioration_regressor.json"
METADATA_PATH = MODELS_DIR / "road_prediction_metadata.json"

VERSION = "1.0.0"


def load_model_artifacts() -> Tuple[xgb.XGBClassifier | None, xgb.XGBRegressor | None, Dict[str, Any] | None]:
    """
    Load saved XGBoost models and version metadata from disk.
    Returns:
        classifier, regressor, metadata
    """
    clf = None
    reg = None
    meta = None

    if CLASSIFIER_PATH.exists():
        clf = xgb.XGBClassifier()
        clf.load_model(str(CLASSIFIER_PATH))

    if REGRESSOR_PATH.exists():
        reg = xgb.XGBRegressor()
        reg.load_model(str(REGRESSOR_PATH))

    if METADATA_PATH.exists():
        try:
            with open(METADATA_PATH, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except Exception:
            meta = None

    return clf, reg, meta


def train_and_save_pipeline(
    df: pd.DataFrame,
    high_priority_threshold: int = 65,
    is_synthetic: bool = True
) -> Dict[str, Any]:
    """
    Full chronological training pipeline:
    1. Extracts features and classification/regression targets.
    2. Splits chronologically (first 80% for training, last 20% for validation).
    3. Trains XGBClassifier and XGBRegressor with explicit seeds.
    4. Evaluates predictions.
    5. Saves model artifacts and metadata.
    """
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Process features and targets
    X, y_class, y_reg, df_clean = extract_features_and_targets(df, high_priority_threshold)

    # Validate that we have sufficient samples and at least two classes in classifier target
    if len(X) < 10:
        raise ValueError(f"Insufficient training samples: got {len(X)} records, minimum required is 10.")
    
    unique_classes = np.unique(y_class)
    if len(unique_classes) < 2:
        raise ValueError("Training dataset lacks class diversity (must contain both high-priority and normal cases).")

    # 2. Chronological Train-Validation Split
    # Sort entire dataset chronologically to prevent future target leakage
    sorted_indices = df_clean["timestamp"].sort_values().index
    X_sorted = X.loc[sorted_indices]
    y_class_sorted = y_class.loc[sorted_indices]
    y_reg_sorted = y_reg.loc[sorted_indices]

    split_idx = int(len(X_sorted) * 0.8)
    
    X_train, X_val = X_sorted.iloc[:split_idx], X_sorted.iloc[split_idx:]
    y_class_train, y_class_val = y_class_sorted.iloc[:split_idx], y_class_sorted.iloc[split_idx:]
    y_reg_train, y_reg_val = y_reg_sorted.iloc[:split_idx], y_reg_sorted.iloc[split_idx:]

    # 3. Train Models
    # XGBClassifier
    clf = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.05,
        random_state=42,
        eval_metric="logloss"
    )
    clf.fit(X_train, y_class_train)

    # XGBRegressor
    reg = xgb.XGBRegressor(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.05,
        random_state=42,
        eval_metric="rmse"
    )
    reg.fit(X_train, y_reg_train)

    # 4. Evaluate on Validation Set
    class_preds = clf.predict_proba(X_val)[:, 1]
    reg_preds = reg.predict(X_val)

    class_metrics = evaluate_classifier(y_class_val, class_preds)
    reg_metrics = evaluate_regressor(y_reg_val, reg_preds)

    # 5. Save Artifacts
    clf.save_model(str(CLASSIFIER_PATH))
    reg.save_model(str(REGRESSOR_PATH))

    metadata = {
        "version": VERSION,
        "training_date": datetime.now(timezone.utc).isoformat(),
        "feature_count": len(FEATURE_COLS),
        "feature_names": FEATURE_COLS,
        "training_sample_count": len(X_train),
        "validation_sample_count": len(X_val),
        "is_synthetic": is_synthetic,
        "target_definition": f"Priority score >= {high_priority_threshold} in next period",
        "validation_metrics": {
            "classifier": class_metrics,
            "regressor": reg_metrics
        }
    }

    with open(METADATA_PATH, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=4)

    return metadata
