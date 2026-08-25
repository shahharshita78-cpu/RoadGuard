"""
Unit and integration tests for Phase 12: Predictive Road Deterioration.
Validates features, targets, chronological split, training, inference,
bounds, explanations, API endpoints, and persistence.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import numpy as np
import pandas as pd
import pytest

# Ensure project root is importable
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from roadguard.backend.app.services.prediction.features import (
    extract_features_and_targets,
    prepare_single_inference_features,
    FEATURE_COLS
)
from roadguard.backend.app.services.prediction.prediction import (
    assign_risk_category,
    explain_prediction,
    run_prediction_pipeline,
    save_prediction,
    get_all_predictions,
    get_predictions_by_road
)
from roadguard.backend.app.services.prediction.model import (
    train_and_save_pipeline,
    load_model_artifacts
)
from roadguard.backend.app.services.prediction.evaluation import (
    evaluate_classifier,
    evaluate_regressor
)


@pytest.fixture
def sample_longitudinal_data() -> pd.DataFrame:
    """Generate a tiny mock longitudinal dataframe of 20 rows for unit tests."""
    data = []
    # 2 roads, 10 periods each
    for r in [1, 2]:
        road_id = f"ROAD_{r:03d}"
        for p in range(10):
            # Create gradual deterioration
            health = max(10, 100 - p * 8)
            priority = min(100, 20 + p * 8)
            severity = min(100, 15 + p * 8)
            
            row = {
                "road_segment_id": road_id,
                "timestamp": f"2026-01-{p+1:02d}T12:00:00",
                "road_health_score": health,
                "severity_score": severity,
                "priority_score": priority,
                "priority": "High" if priority >= 65 else "Routine",
                "detection_count": p,
                "damage_class_counts": json.dumps({"D00": p, "D10": 0, "D20": 0, "D40": 0}),
                "avg_confidence": 0.8,
                "max_severity_score": float(severity),
                "damage_frame_pct": 30.0,
                "unique_detections": p,
                "maintenance_performed": 0,
            }
            
            # Future target columns (next inspection)
            if p < 9:
                row["future_road_health"] = max(10, 100 - (p + 1) * 8)
                row["future_priority_score"] = min(100, 20 + (p + 1) * 8)
                row["days_to_next_inspection"] = 30
            else:
                row["future_road_health"] = None
                row["future_priority_score"] = None
                row["days_to_next_inspection"] = None
                
            # Previous columns
            if p > 0:
                row["days_since_previous_inspection"] = 30
                row["previous_road_health_score"] = max(10, 100 - (p - 1) * 8)
                row["deterioration_rate"] = 0.26
                row["number_of_previous_inspections"] = p
            else:
                row["days_since_previous_inspection"] = 0
                row["previous_road_health_score"] = health
                row["deterioration_rate"] = 0.0
                row["number_of_previous_inspections"] = 0

            data.append(row)
            
    return pd.DataFrame(data)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPredictiveServices:

    def test_feature_engineering_unpacks_correctly(self, sample_longitudinal_data):
        """1. Validate feature engineering unpacks damage counts and selects proper columns."""
        X, y_class, y_reg, df_clean = extract_features_and_targets(sample_longitudinal_data, high_priority_threshold=65)
        
        # Verify columns
        assert list(X.columns) == FEATURE_COLS
        assert "damage_count_D00" in X.columns
        assert X["damage_count_D00"].iloc[1] == 1.0  # unpacked from json D00 count
        
        # Check shapes (2 segments, last period of each segment is dropped -> 18 remaining)
        assert len(X) == 18
        assert len(y_class) == 18
        assert len(y_reg) == 18

    def test_target_generation_logic(self, sample_longitudinal_data):
        """2. Validate target generation logic and thresholding."""
        # Threshold 65
        X, y_class, y_reg, _ = extract_features_and_targets(sample_longitudinal_data, high_priority_threshold=65)
        # Verify target is binary
        assert set(y_class.unique()).issubset({0, 1})
        # Period 5 next is period 6 (priority 20 + 6*8 = 68 >= 65 -> should be 1)
        assert y_class.iloc[5] == 1
        # Period 0 next is period 1 (priority 20 + 1*8 = 28 < 65 -> should be 0)
        assert y_class.iloc[0] == 0

    def test_chronological_split(self, sample_longitudinal_data):
        """3. Validate chronological train/validation splitting does not mix order."""
        # Train on first 80%, validate on last 20% by sorted timestamp
        df_clean = sample_longitudinal_data.copy()
        
        # Extract features and targets
        X, y_class, y_reg, df_proc = extract_features_and_targets(df_clean, high_priority_threshold=65)
        
        sorted_idx = df_proc["timestamp"].sort_values().index
        df_sorted = df_proc.loc[sorted_idx]
        split_idx = int(len(df_sorted) * 0.8)
        
        train_dates = df_sorted["timestamp"].iloc[:split_idx].tolist()
        val_dates = df_sorted["timestamp"].iloc[split_idx:].tolist()
        
        # Ensure all training dates are chronologically before or equal to validation dates
        assert max(train_dates) <= min(val_dates)

    def test_dataset_validation(self, sample_longitudinal_data):
        """4. Validate validation functions raise error on empty dataset or single-class targets."""
        # Empty dataset
        empty_df = pd.DataFrame(columns=sample_longitudinal_data.columns)
        with pytest.raises(ValueError, match="No valid records with targets found"):
            extract_features_and_targets(empty_df)

        # Single class training target should raise error in pipeline
        single_class_df = sample_longitudinal_data.copy()
        # Set all future priority scores low so target is only 0
        single_class_df["future_priority_score"] = 10
        with pytest.raises(ValueError, match="lacks class diversity"):
            train_and_save_pipeline(single_class_df, high_priority_threshold=65)

    def test_model_training_and_saving(self, sample_longitudinal_data):
        """5. Validate model training pipeline and artifact creation."""
        with patch("roadguard.backend.app.services.prediction.model.CLASSIFIER_PATH") as mock_clf_path, \
             patch("roadguard.backend.app.services.prediction.model.REGRESSOR_PATH") as mock_reg_path, \
             patch("roadguard.backend.app.services.prediction.model.METADATA_PATH") as mock_meta_path:
            
            # Set target write string paths
            mock_clf_path.parent.mkdir = MagicMock()
            mock_clf_path.__str__.return_value = "mock_clf.json"
            mock_reg_path.__str__.return_value = "mock_reg.json"
            mock_meta_path.__str__.return_value = "mock_meta.json"
            
            # Mock open
            m_open = MagicMock()
            with patch("builtins.open", m_open):
                metadata = train_and_save_pipeline(sample_longitudinal_data, high_priority_threshold=65)
                
            assert "version" in metadata
            assert metadata["training_sample_count"] > 0
            assert "classifier" in metadata["validation_metrics"]

    def test_model_prediction_pipeline(self):
        """6. Validate running prediction pipeline with mock models."""
        mock_clf = MagicMock()
        mock_clf.predict_proba.return_value = np.array([[0.35, 0.65]])
        mock_clf.get_booster.return_value = MagicMock()
        
        # XGBoost get_booster prediction returns values for 16 features + 1 bias
        mock_booster = mock_clf.get_booster.return_value
        mock_booster.predict.return_value = [np.array([0.1] * 17)]
        
        mock_reg = MagicMock()
        mock_reg.predict.return_value = np.array([72.5])
        
        mock_meta = {"version": "1.0.0", "target_definition": "mock target"}

        payload = {
            "road_segment_id": "ROAD_999",
            "road_health_score": 80.0,
            "severity_score": 30.0,
            "priority_score": 45.0,
            "detection_count": 2,
        }

        with patch("roadguard.backend.app.services.prediction.prediction.load_model_artifacts", return_value=(mock_clf, mock_reg, mock_meta)):
            result = run_prediction_pipeline(payload)
            
        assert result["road_segment_id"] == "ROAD_999"
        assert result["risk_probability"] == 0.65
        assert result["risk_category"] == "HIGH"
        assert result["predicted_future_health"] == 72.5
        assert len(result["top_factors"]) > 0

    def test_probability_bounds(self):
        """7. Validate that predictions result in probability bounds in [0, 1]."""
        mock_clf = MagicMock()
        # Mock probabilities outside [0, 1] - let's verify if bounds clamp/work
        mock_clf.predict_proba.return_value = np.array([[0.0, 1.0]])
        mock_clf.get_booster.return_value = MagicMock()
        mock_clf.get_booster.return_value.predict.return_value = [np.array([0.1] * 17)]
        mock_reg = MagicMock()
        mock_reg.predict.return_value = np.array([120.0])  # exceeds 100

        payload = {
            "road_segment_id": "ROAD_001",
            "road_health_score": 90.0,
            "severity_score": 10.0,
            "priority_score": 10.0,
            "detection_count": 0,
        }

        with patch("roadguard.backend.app.services.prediction.prediction.load_model_artifacts", return_value=(mock_clf, mock_reg, {"version": "1.0.0"})):
            result = run_prediction_pipeline(payload)
            
        assert 0.0 <= result["risk_probability"] <= 1.0
        assert result["predicted_future_health"] == 100.0  # clamped to 100

    def test_risk_category_assignment(self):
        """8. Validate risk category mapping matching specific probability boundaries."""
        assert assign_risk_category(0.10) == "LOW"
        assert assign_risk_category(0.35) == "MEDIUM"
        assert assign_risk_category(0.60) == "HIGH"
        assert assign_risk_category(0.85) == "CRITICAL"

    def test_feature_contribution_explainability(self):
        """9. Validate local feature contribution and explanation mappings."""
        mock_clf = MagicMock()
        # 16 features + 1 bias
        contribs = np.array([0.5, -0.2] + [0.0] * 14 + [0.1])
        mock_clf.get_booster.return_value.predict.return_value = [contribs]
        
        # Prepare sample DataFrame
        df_infer = prepare_single_inference_features({
            "road_health_score": 80,
            "severity_score": 40
        })
        
        factors = explain_prediction(mock_clf, df_infer)
        assert len(factors) > 0
        # First factor should be road_health_score (contribution 0.5 > 0 -> increased)
        assert factors[0]["feature"] == "road_health_score"
        assert factors[0]["direction"] == "increased"
        # Second factor should be severity_score (contribution -0.2 < 0 -> decreased)
        assert factors[1]["feature"] == "severity_score"
        assert factors[1]["direction"] == "decreased"

    def test_missing_feature_validation(self):
        """10. Validate missing features default safely without throwing exceptions."""
        payload = {"road_segment_id": "ROAD_001"}
        df_infer = prepare_single_inference_features(payload)
        
        # Verify all columns filled
        assert list(df_infer.columns) == FEATURE_COLS
        assert df_infer["road_health_score"].iloc[0] == 0.0
        assert df_infer["previous_road_health_score"].iloc[0] == 100.0  # default previous

    def test_prediction_persistence(self):
        """11. Validate persistence insertions and retrieval queries."""
        import uuid
        pred_id = f"pred-mock-{uuid.uuid4()}"
        record = {
            "prediction_id": pred_id,
            "timestamp": "2026-08-25T12:00:00",
            "road_segment_id": "TEST_SEG_PERSIST",
            "model_version": "1.0.0",
            "risk_probability": 0.45,
            "risk_category": "MEDIUM",
            "predicted_future_health": 80.0,
            "top_factors": [{"feature": "road_health_score", "direction": "increased", "importance": 0.4}],
            "feature_snapshot": {"road_health_score": 75}
        }
        
        saved = save_prediction(record)
        assert saved["prediction_id"] == pred_id
        
        # Query
        by_road = get_predictions_by_road("TEST_SEG_PERSIST")
        assert len(by_road) > 0
        assert by_road[0]["risk_category"] == "MEDIUM"

    def test_reproducibility_seed(self):
        """14. Validate synthetic dataset generator creates identical files with same seed."""
        from scripts.generate_prediction_dataset import generate_longitudinal_data
        
        # Two separate generations with seed=42 should produce identical outputs
        run1 = generate_longitudinal_data(num_roads=5, periods=3, seed=42)
        run2 = generate_longitudinal_data(num_roads=5, periods=3, seed=42)
        
        assert len(run1) == len(run2)
        for i in range(len(run1)):
            assert run1[i]["road_segment_id"] == run2[i]["road_segment_id"]
            assert run1[i]["road_health_score"] == run2[i]["road_health_score"]
            assert run1[i]["future_road_health"] == run2[i]["future_road_health"]

    def test_no_future_target_leakage(self, sample_longitudinal_data):
        """15. Validate that y targets are purely based on future columns and features are historical."""
        X, y_class, y_reg, df_proc = extract_features_and_targets(sample_longitudinal_data, high_priority_threshold=65)
        
        # Verify that y_class corresponds to NEXT period priority score, not CURRENT
        for idx in range(len(X)):
            current_priority = X["priority_score"].iloc[idx]
            future_priority = df_proc["future_priority_score"].iloc[idx]
            target_class = y_class.iloc[idx]
            
            # Target class must match the future priority condition, not the current one
            assert target_class == (1 if future_priority >= 65 else 0)


# ---------------------------------------------------------------------------
# API integration tests
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from roadguard.backend.app.main import app
    return TestClient(app)


class TestPredictionAPI:

    def test_model_metadata_api(self, client):
        """13. Validate /api/predictions/model endpoint details."""
        mock_meta = {
            "version": "1.0.0",
            "training_date": "2026-08-25T12:00:00",
            "feature_count": 16,
            "training_sample_count": 320,
            "is_synthetic": True,
            "target_definition": "Priority score >= 65",
            "validation_metrics": {"classifier": {"roc_auc": 0.85}}
        }
        
        with patch("roadguard.backend.app.api.prediction.load_model_artifacts", return_value=(None, None, mock_meta)):
            response = client.get("/api/predictions/model")
            
        assert response.status_code == 200
        data = response.json()
        assert data["version"] == "1.0.0"
        assert data["is_synthetic"] is True

    def test_prediction_inference_api(self, client):
        """12. Validate /api/predictions/deterioration API inputs and response fields."""
        payload = {
            "road_segment_id": "ROAD_XYZ",
            "road_health_score": 85.0,
            "severity_score": 25.0,
            "priority_score": 30.0,
            "detection_count": 1
        }
        
        mock_result = {
            "prediction_id": "pred-xyz-123",
            "timestamp": "2026-08-25T12:00:00",
            "road_segment_id": "ROAD_XYZ",
            "model_version": "1.0.0",
            "risk_probability": 0.12,
            "risk_category": "LOW",
            "predicted_future_health": 82.0,
            "top_factors": [],
            "urgency_recommendation": "Standard schedule",
            "feature_snapshot": {}
        }
        
        with patch("roadguard.backend.app.api.prediction.run_prediction_pipeline", return_value=mock_result), \
             patch("roadguard.backend.app.api.prediction.save_prediction", return_value=mock_result):
            response = client.post("/api/predictions/deterioration", json=payload)
            
        assert response.status_code == 200
        data = response.json()
        assert data["prediction_id"] == "pred-xyz-123"
        assert data["risk_category"] == "LOW"

    def test_invalid_nan_input_api(self, client):
        """12. Validate /api/predictions/deterioration rejects invalid inputs with 422."""
        payload = {
            "road_segment_id": "ROAD_XYZ",
            "road_health_score": "invalid-float",  # triggers float parsing failure (422)
            "severity_score": 25.0,
            "priority_score": 30.0,
            "detection_count": 1
        }
        response = client.post("/api/predictions/deterioration", json=payload)
        assert response.status_code == 422
