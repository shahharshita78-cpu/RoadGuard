import io
import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# Mock data resembling raw ONNX output containing only very low confidence detections (representing Image 2)
# The output shape is (1, 8, 8400) or similar.
# To make it super simple, we can patch 'roadguard.backend.app.services.detector.run_inference'
# or patch the ONNX session's 'run' method. Let's patch 'run_inference' directly to return low conf detections.

@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from roadguard.backend.app.main import app
    return TestClient(app)

def test_inference_below_threshold(client):
    # Mock run_inference to return a single low confidence detection (0.046 confidence) representing Image 2
    mock_dets = [
        {
            "damage_class": "Potholes",
            "confidence": 0.046,
            "bbox": {"x1": 536, "y1": 872, "x2": 1174, "y2": 1198}
        }
    ]
    
    with patch("roadguard.backend.app.services.detector.run_inference", return_value=(mock_dets, 1280, 720)):
        # Execute inspection with confidence=0.40 (which is the frontend default user setting)
        # Even though run_inference returned mock_dets, the endpoint filters detections based on the target confidence?
        # Wait, let's verify if the endpoint itself filters or if detector.run_inference does.
        # In detection.py:
        # raw_detections, img_w, img_h = detector.run_inference(file_bytes, confidence)
        # This means the thresholding happens INSIDE detector.run_inference!
        # So we should patch the ONNX run call, OR patch run_inference to dynamically filter.
        
        # Let's write a dynamic mock for run_inference:
        def dynamic_run_inference(image_bytes, confidence_threshold):
            # Only return detections that meet the threshold
            filtered = [d for d in mock_dets if d["confidence"] >= confidence_threshold]
            return filtered, 1280, 720
            
        with patch("roadguard.backend.app.services.detector.run_inference", side_effect=dynamic_run_inference):
            # Test at 0.40 confidence (defect count should be 0 because 0.046 < 0.40)
            response = client.post(
                "/api/detect",
                files={"file": ("test.jpg", io.BytesIO(b"dummy image data"), "image/jpeg")},
                data={"confidence": 0.40}
            )
            assert response.status_code == 200
            data = response.json()
            assert data["detection_count"] == 0
            assert len(data["detections"]) == 0
            assert data["severity"]["severity_score"] == 0
            assert data["road_health"]["road_health_score"] == 100

def test_invalid_confidence_threshold_low(client):
    # Confidence below 0.05 should return 422 validation error (due to FastAPI ge=0.05 constraint)
    response = client.post(
        "/api/detect",
        files={"file": ("test.jpg", io.BytesIO(b"dummy image data"), "image/jpeg")},
        data={"confidence": 0.02}
    )
    assert response.status_code == 422
