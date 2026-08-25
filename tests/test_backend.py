"""
Unit tests for RoadGuard backend services and API endpoints.

Run from the repository root inside the virtual environment:
    .venv\\Scripts\\pytest tests/ -v
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

# Make the repo root importable
sys.path.insert(0, str(Path(__file__).parents[1]))


# ---------------------------------------------------------------------------
# Severity service tests
# ---------------------------------------------------------------------------

class TestSeverityService:
    def test_no_detections_returns_zero(self):
        from roadguard.backend.app.services.severity import compute_severity
        result = compute_severity([], 640, 480)
        assert result["severity_score"] == 0
        assert result["severity"] == "Low"

    def test_pothole_scores_higher_than_crack(self):
        from roadguard.backend.app.services.severity import compute_severity
        crack = [{"damage_class": "D00", "confidence": 0.8, "bbox": {"x1": 0, "y1": 0, "x2": 100, "y2": 100}}]
        pothole = [{"damage_class": "D40", "confidence": 0.8, "bbox": {"x1": 0, "y1": 0, "x2": 100, "y2": 100}}]
        crack_score = compute_severity(crack, 640, 480)["severity_score"]
        pothole_score = compute_severity(pothole, 640, 480)["severity_score"]
        assert pothole_score > crack_score

    def test_score_bounded_0_100(self):
        from roadguard.backend.app.services.severity import compute_severity
        big_detections = [
            {"damage_class": "D40", "confidence": 1.0, "bbox": {"x1": 0, "y1": 0, "x2": 640, "y2": 480}}
            for _ in range(10)
        ]
        result = compute_severity(big_detections, 640, 480)
        assert 0 <= result["severity_score"] <= 100

    def test_severity_labels(self):
        from roadguard.backend.app.services.severity import compute_severity
        # Single small detection with low-severity class should be Low
        low_det = [{"damage_class": "D00", "confidence": 0.3, "bbox": {"x1": 0, "y1": 0, "x2": 10, "y2": 10}}]
        result = compute_severity(low_det, 640, 480)
        assert result["severity"] in {"Low", "Medium", "High"}


# ---------------------------------------------------------------------------
# Road health index tests
# ---------------------------------------------------------------------------

class TestRoadHealthService:
    def test_no_detections_returns_100(self):
        from roadguard.backend.app.services.scoring import compute_road_health
        result = compute_road_health([], 640, 480)
        assert result["road_health_score"] == 100
        assert result["road_condition"] == "Excellent"

    def test_score_bounded_0_100(self):
        from roadguard.backend.app.services.scoring import compute_road_health
        big_detections = [
            {"damage_class": "D40", "confidence": 1.0, "bbox": {"x1": 0, "y1": 0, "x2": 640, "y2": 480}}
            for _ in range(15)
        ]
        result = compute_road_health(big_detections, 640, 480)
        assert 0 <= result["road_health_score"] <= 100

    def test_more_damage_lowers_score(self):
        from roadguard.backend.app.services.scoring import compute_road_health
        few = [{"damage_class": "D10", "confidence": 0.7, "bbox": {"x1": 0, "y1": 0, "x2": 50, "y2": 50}}]
        many = few * 8
        few_score = compute_road_health(few, 640, 480)["road_health_score"]
        many_score = compute_road_health(many, 640, 480)["road_health_score"]
        assert many_score < few_score

    def test_condition_labels_valid(self):
        from roadguard.backend.app.services.scoring import compute_road_health
        valid_conditions = {"Excellent", "Good", "Moderate", "Poor", "Critical"}
        result = compute_road_health([], 640, 480)
        assert result["road_condition"] in valid_conditions


# ---------------------------------------------------------------------------
# Maintenance priority tests
# ---------------------------------------------------------------------------

class TestMaintenancePriority:
    def test_high_severity_low_health_gives_high_priority(self):
        from roadguard.backend.app.services.optimizer import compute_maintenance_priority
        result = compute_maintenance_priority(90, 10, 8)
        assert result["priority"] in {"Immediate", "High"}
        assert result["priority_score"] >= 65

    def test_low_severity_good_health_gives_low_priority(self):
        from roadguard.backend.app.services.optimizer import compute_maintenance_priority
        result = compute_maintenance_priority(5, 95, 0)
        assert result["priority"] in {"Routine", "Medium"}

    def test_score_bounded_0_100(self):
        from roadguard.backend.app.services.optimizer import compute_maintenance_priority
        result = compute_maintenance_priority(100, 0, 20)
        assert 0 <= result["priority_score"] <= 100

    def test_reasons_is_nonempty_list(self):
        from roadguard.backend.app.services.optimizer import compute_maintenance_priority
        result = compute_maintenance_priority(50, 50, 3)
        assert isinstance(result["reasons"], list)
        assert len(result["reasons"]) >= 1

    def test_priority_labels_valid(self):
        from roadguard.backend.app.services.optimizer import compute_maintenance_priority
        valid_labels = {"Immediate", "High", "Medium", "Routine"}
        result = compute_maintenance_priority(50, 50, 3)
        assert result["priority"] in valid_labels


# ---------------------------------------------------------------------------
# GPS extraction tests
# ---------------------------------------------------------------------------

class TestGPSExtraction:
    def test_returns_none_for_non_image_bytes(self):
        from roadguard.backend.app.services.gps import extract_gps_from_bytes
        result = extract_gps_from_bytes(b"not an image")
        assert result is None

    def test_returns_none_for_empty_bytes(self):
        from roadguard.backend.app.services.gps import extract_gps_from_bytes
        result = extract_gps_from_bytes(b"")
        assert result is None

    def test_extracts_coords_from_gps_jpeg(self):
        """Verify GPS extraction from the sample JPEG that has known coordinates."""
        from roadguard.backend.app.services.gps import extract_gps_from_bytes
        sample = Path(__file__).parents[1] / "IMG_7002.jpg"
        if not sample.exists():
            pytest.skip("Sample GPS image not available")
        coords = extract_gps_from_bytes(sample.read_bytes())
        assert coords is not None
        lat, lon = coords
        # Known approximate location (Pune, India)
        assert 18.0 < lat < 19.0
        assert 73.0 < lon < 74.0


# ---------------------------------------------------------------------------
# Detector model availability test
# ---------------------------------------------------------------------------

class TestDetector:
    def test_model_file_exists(self):
        from roadguard.backend.app.services.detector import is_model_available
        assert is_model_available(), "road_damage.pt not found in models/"


# ---------------------------------------------------------------------------
# FastAPI endpoint tests
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from roadguard.backend.app.main import app
    return TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "model_loaded" in data
        assert "version" in data


class TestInspectionsEndpoint:
    def test_list_inspections_returns_list(self, client):
        response = client.get("/api/inspections")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_missing_inspection_returns_404(self, client):
        response = client.get("/api/inspections/nonexistent-id")
        assert response.status_code == 404


class TestAnalyticsEndpoint:
    def test_summary_returns_expected_keys(self, client):
        response = client.get("/api/analytics/summary")
        assert response.status_code == 200
        data = response.json()
        for key in ("total_inspections", "total_detections", "avg_road_health"):
            assert key in data


class TestMaintenanceEndpoint:
    def test_priority_compute_valid_input(self, client):
        response = client.post(
            "/api/maintenance/priority",
            json={"severity_score": 70, "road_health_score": 40, "detection_count": 5},
        )
        assert response.status_code == 200
        data = response.json()
        assert "priority_score" in data
        assert "priority" in data
        assert "reasons" in data

    def test_maintenance_queue_returns_list(self, client):
        response = client.get("/api/maintenance/queue")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
