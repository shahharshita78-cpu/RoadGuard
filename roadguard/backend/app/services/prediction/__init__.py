"""
RoadGuard Predictive Analytics Service.
"""
from __future__ import annotations

from .data import load_raw_dataset
from .model import train_and_save_pipeline, load_model_artifacts
from .prediction import (
    run_prediction_pipeline,
    get_all_predictions,
    get_predictions_by_road,
    save_prediction,
    ensure_prediction_schema
)
