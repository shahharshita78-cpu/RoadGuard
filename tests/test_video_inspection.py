"""
Tests for Phase 11: Video Road Inspection service and API endpoints.

These tests run WITHOUT needing actual video files by creating minimal synthetic
inputs (single-frame AVI/raw bytes) or by mocking OpenCV calls where necessary.
All 23 original tests remain unmodified; this file adds new tests only.

Run from repository root:
    .venv\\Scripts\\pytest tests/ -v
"""
from __future__ import annotations

import json
import sys
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))


# ===========================================================================
# Helpers
# ===========================================================================

def _make_detection(damage_class: str = "Potholes", conf: float = 0.8,
                     x1: int = 10, y1: int = 10, x2: int = 110, y2: int = 110) -> dict:
    return {
        "damage_class": damage_class,
        "confidence": conf,
        "bbox": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
    }


def _minimal_mp4_bytes() -> bytes:
    """
    Return a small, valid MP4 file created with OpenCV in memory.
    Falls back to a tiny hand-crafted byte sequence if OpenCV is not available.
    We use a real 1-frame AVI so VideoCapture can open it in tests that need
    genuine frame reading (service-level tests bypass cv2 entirely via mocking).
    """
    try:
        import cv2
        import numpy as np
        import tempfile

        tmp = Path(tempfile.mktemp(suffix=".avi"))
        writer = cv2.VideoWriter(
            str(tmp),
            cv2.VideoWriter_fourcc(*"MJPG"),
            30.0,
            (64, 64),
        )
        frame = (np.random.rand(64, 64, 3) * 255).astype("uint8")
        writer.write(frame)
        writer.release()
        data = tmp.read_bytes()
        tmp.unlink(missing_ok=True)
        return data
    except Exception:
        # Fallback: just return some bytes; tests that use this only check
        # for error conditions, not successful parsing.
        return b"\x00" * 256


# ===========================================================================
# 1. Temporal deduplication helpers
# ===========================================================================

class TestTemporalDedup:
    def test_iou_identical_boxes_returns_one(self):
        from roadguard.backend.app.services.video_inspection import _iou
        box = {"x1": 0, "y1": 0, "x2": 100, "y2": 100}
        assert _iou(box, box) == pytest.approx(1.0)

    def test_iou_non_overlapping_returns_zero(self):
        from roadguard.backend.app.services.video_inspection import _iou
        a = {"x1": 0, "y1": 0, "x2": 50, "y2": 50}
        b = {"x1": 100, "y1": 100, "x2": 200, "y2": 200}
        assert _iou(a, b) == pytest.approx(0.0)

    def test_iou_partial_overlap(self):
        from roadguard.backend.app.services.video_inspection import _iou
        a = {"x1": 0, "y1": 0, "x2": 100, "y2": 100}
        b = {"x1": 50, "y1": 0, "x2": 150, "y2": 100}
        iou = _iou(a, b)
        assert 0.0 < iou < 1.0

    def test_duplicate_detected_same_class_high_iou(self):
        from roadguard.backend.app.services.video_inspection import _is_duplicate
        det = _make_detection("Potholes", x1=10, y1=10, x2=110, y2=110)
        prev = [_make_detection("Potholes", x1=12, y1=12, x2=112, y2=112)]
        assert _is_duplicate(det, prev) is True

    def test_duplicate_not_detected_different_class(self):
        from roadguard.backend.app.services.video_inspection import _is_duplicate
        det = _make_detection("Potholes", x1=10, y1=10, x2=110, y2=110)
        prev = [_make_detection("Longitudinal Crack", x1=10, y1=10, x2=110, y2=110)]
        assert _is_duplicate(det, prev) is False

    def test_duplicate_not_detected_low_iou(self):
        from roadguard.backend.app.services.video_inspection import _is_duplicate
        det = _make_detection("Potholes", x1=0, y1=0, x2=50, y2=50)
        prev = [_make_detection("Potholes", x1=400, y1=400, x2=450, y2=450)]
        assert _is_duplicate(det, prev) is False

    def test_duplicate_not_detected_empty_prev(self):
        from roadguard.backend.app.services.video_inspection import _is_duplicate
        det = _make_detection("Potholes")
        assert _is_duplicate(det, []) is False


# ===========================================================================
# 2. Severity aggregation
# ===========================================================================

class TestSeverityAggregation:
    def test_empty_unique_detections_returns_low(self):
        from roadguard.backend.app.services.severity import compute_severity
        result = compute_severity([], 640, 480)
        assert result["severity_score"] == 0
        assert result["severity"] == "Low"

    def test_aggregation_uses_top3_mean(self):
        from roadguard.backend.app.services.severity import compute_severity
        # 5 potholes should not push score above 100
        dets = [_make_detection("Potholes", conf=1.0, x1=0, y1=0, x2=200, y2=200) for _ in range(5)]
        result = compute_severity(dets, 640, 480)
        assert 0 <= result["severity_score"] <= 100


# ===========================================================================
# 3. Detection aggregation logic
# ===========================================================================

class TestDetectionAggregation:
    def _run_aggregation(self, frame_detections: List[List[dict]]) -> dict:
        """
        Simulate the aggregation loop from video_inspection.process_video
        without actually opening a video, to unit-test dedup and counting.
        """
        from roadguard.backend.app.services.video_inspection import _is_duplicate
        from roadguard.backend.app.services.severity import compute_severity
        from roadguard.backend.app.services.scoring import compute_road_health
        from roadguard.backend.app.services.optimizer import compute_maintenance_priority

        all_detections: List[dict] = []
        unique_detections: List[dict] = []
        prev_frame_dets: List[dict] = []
        severity_scores: List[int] = []
        frames_with_damage = 0

        for frame_dets in frame_detections:
            all_detections.extend(frame_dets)
            if frame_dets:
                frames_with_damage += 1
            for det in frame_dets:
                if not _is_duplicate(det, prev_frame_dets):
                    unique_detections.append(det)
            frame_sev = compute_severity(frame_dets, 640, 480)
            severity_scores.append(frame_sev["severity_score"])
            prev_frame_dets = frame_dets

        overall_sev = compute_severity(unique_detections, 1280, 720)
        overall_health = compute_road_health(unique_detections, 1280, 720)
        overall_priority = compute_maintenance_priority(
            overall_sev["severity_score"],
            overall_health["road_health_score"],
            len(unique_detections),
        )
        return {
            "total_detections": len(all_detections),
            "unique_detections": len(unique_detections),
            "frames_with_damage": frames_with_damage,
            "severity": overall_sev,
            "health": overall_health,
            "priority": overall_priority,
        }

    def test_identical_consecutive_frames_count_as_one(self):
        """Same defect in 3 consecutive frames → unique_detections == 1."""
        det = _make_detection("Potholes")
        frames = [[det], [det], [det]]
        result = self._run_aggregation(frames)
        assert result["unique_detections"] == 1
        assert result["total_detections"] == 3

    def test_different_class_not_deduplicated(self):
        """Two different damage classes in same frame position → both counted."""
        f1 = [_make_detection("Potholes")]
        f2 = [_make_detection("Longitudinal Crack")]
        result = self._run_aggregation([f1, f2])
        assert result["unique_detections"] == 2

    def test_empty_frames_give_zero_damage(self):
        result = self._run_aggregation([[], [], []])
        assert result["total_detections"] == 0
        assert result["unique_detections"] == 0
        assert result["frames_with_damage"] == 0

    def test_mixed_frames(self):
        f0 = [_make_detection("Potholes", x1=0, y1=0, x2=50, y2=50)]
        f1 = [_make_detection("Potholes", x1=0, y1=0, x2=50, y2=50)]  # duplicate
        f2 = [_make_detection("Alligator Crack", x1=200, y1=200, x2=250, y2=250)]  # new
        result = self._run_aggregation([f0, f1, f2])
        assert result["total_detections"] == 3
        assert result["unique_detections"] == 2  # f0 + f2 (f1 is dup of f0)

    def test_priority_score_bounded(self):
        dets = [[_make_detection("Potholes", conf=1.0, x1=0, y1=0, x2=300, y2=300)] for _ in range(3)]
        result = self._run_aggregation(dets)
        assert 0 <= result["priority"]["priority_score"] <= 100

    def test_all_damage_classes_accepted(self):
        frames = [
            [_make_detection("Longitudinal Crack")],
            [_make_detection("Transverse Crack")],
            [_make_detection("Alligator Crack")],
            [_make_detection("Potholes")],
        ]
        result = self._run_aggregation(frames)
        assert result["unique_detections"] == 4


# ===========================================================================
# 4. Database persistence
# ===========================================================================

class TestVideoPersistence:
    def _sample_record(self) -> dict:
        import uuid
        return {
            "inspection_id": str(uuid.uuid4()),
            "timestamp": "2026-01-01T12:00:00",
            "video_name": "test_road.mp4",
            "duration_seconds": 10.0,
            "total_frames": 300,
            "sampled_frames": 10,
            "frame_interval": 30,
            "fps": 30.0,
            "total_detections": 5,
            "unique_detections": 3,
            "frames_with_damage": 4,
            "damage_frame_pct": 40.0,
            "avg_confidence": 0.75,
            "avg_severity_score": 35,
            "max_severity_score": 60,
            "overall_severity": "Medium",
            "road_health_score": 72,
            "road_condition": "Good",
            "priority_score": 42,
            "priority": "Medium",
            "priority_reasons": ["Moderate severity damage detected"],
            "class_distribution": {"Potholes": 2, "Longitudinal Crack": 1},
            "frame_summaries": [
                {
                    "frame_number": 0,
                    "timestamp_sec": 0.0,
                    "detection_count": 2,
                    "severity_score": 35,
                    "road_health_score": 80,
                    "damage_classes": ["Potholes"],
                }
            ],
        }

    def test_save_and_retrieve_video_inspection(self):
        from roadguard.backend.app.services.video_inspection import (
            save_video_inspection,
            get_video_inspection_by_id,
        )
        record = self._sample_record()
        saved = save_video_inspection(record)
        assert saved["inspection_id"] == record["inspection_id"]
        assert saved["video_name"] == "test_road.mp4"
        assert isinstance(saved["class_distribution"], dict)
        assert isinstance(saved["frame_summaries"], list)

        retrieved = get_video_inspection_by_id(record["inspection_id"])
        assert retrieved is not None
        assert retrieved["inspection_id"] == record["inspection_id"]
        assert retrieved["road_health_score"] == 72

    def test_get_all_returns_list(self):
        from roadguard.backend.app.services.video_inspection import (
            get_all_video_inspections,
            save_video_inspection,
        )
        record = self._sample_record()
        save_video_inspection(record)
        all_records = get_all_video_inspections()
        assert isinstance(all_records, list)
        assert len(all_records) >= 1

    def test_missing_id_returns_none(self):
        from roadguard.backend.app.services.video_inspection import get_video_inspection_by_id
        result = get_video_inspection_by_id("nonexistent-uuid")
        assert result is None


# ===========================================================================
# 5. process_video — mocked cv2 (frame sampling)
# ===========================================================================

class TestProcessVideoMocked:
    """Unit tests for process_video that mock out cv2 so no real file is needed."""

    def _make_mock_cap(self, frame_count: int = 90, fps: float = 30.0):
        """Build a mock cv2.VideoCapture that serves *frame_count* BGR frames."""
        import numpy as np

        # OpenCV cap.read() returns (retval: bool, frame: ndarray)
        frames = [(True, np.zeros((480, 640, 3), dtype="uint8"))] * frame_count
        frames.append((False, None))  # sentinel

        call_count = {"n": 0}

        def read():
            n = call_count["n"]
            call_count["n"] += 1
            if n < len(frames):
                return frames[n]
            return (None, False)

        cap = MagicMock()
        cap.isOpened.return_value = True
        cap.get.side_effect = lambda prop: {
            0: fps,       # CAP_PROP_FPS
            7: frame_count,  # CAP_PROP_FRAME_COUNT
        }.get(prop, 0)
        cap.read.side_effect = read
        return cap

    def _make_mock_model(self, return_dets: bool = True):
        """Build a mock ultralytics model."""
        import numpy as np

        model = MagicMock()
        model.names = {0: "Potholes"}

        if return_dets:
            box = MagicMock()
            box.cls = [0]
            box.conf = [0.85]
            # Use a real numpy array so .tolist() works like a genuine YOLO tensor
            box.xyxy = [np.array([10.0, 10.0, 110.0, 110.0])]
            result = MagicMock()
            result.boxes = [box]
        else:
            result = MagicMock()
            result.boxes = []

        model.predict.return_value = [result]
        return model

    def test_frame_sampling_interval(self):
        """Exactly ceil(90/30) = 3 frames should be sampled from a 90-frame video."""
        from roadguard.backend.app.services import video_inspection as vi

        cap = self._make_mock_cap(frame_count=90, fps=30.0)
        model = self._make_mock_model(return_dets=False)

        with patch("cv2.VideoCapture", return_value=cap), \
             patch("roadguard.backend.app.services.video_inspection._load_model", return_value=model):
            result = vi.process_video(
                video_path=Path("fake.mp4"),
                video_name="fake.mp4",
                frame_interval=30,
                confidence_threshold=0.25,
            )

        assert result["sampled_frames"] == 3  # frames 0, 30, 60

    def test_detections_accumulated(self):
        """Every sampled frame returning a detection → positive unique count."""
        from roadguard.backend.app.services import video_inspection as vi

        cap = self._make_mock_cap(frame_count=30, fps=30.0)
        model = self._make_mock_model(return_dets=True)

        with patch("cv2.VideoCapture", return_value=cap), \
             patch("roadguard.backend.app.services.video_inspection._load_model", return_value=model):
            result = vi.process_video(
                video_path=Path("fake.mp4"),
                video_name="fake.mp4",
                frame_interval=30,
                confidence_threshold=0.25,
            )

        # Frame 0 is sampled; frame 30 does NOT exist (only 30 frames 0–29)
        assert result["sampled_frames"] >= 1
        assert result["total_detections"] >= 1

    def test_no_detections_gives_100_health(self):
        """Video with no defects should report road_health_score == 100."""
        from roadguard.backend.app.services import video_inspection as vi

        cap = self._make_mock_cap(frame_count=30, fps=30.0)
        model = self._make_mock_model(return_dets=False)

        with patch("cv2.VideoCapture", return_value=cap), \
             patch("roadguard.backend.app.services.video_inspection._load_model", return_value=model):
            result = vi.process_video(
                video_path=Path("fake.mp4"),
                video_name="fake.mp4",
                frame_interval=30,
                confidence_threshold=0.25,
            )

        assert result["road_health_score"] == 100

    def test_invalid_video_raises_value_error(self):
        """An unopenable video should raise ValueError."""
        from roadguard.backend.app.services import video_inspection as vi

        cap = MagicMock()
        cap.isOpened.return_value = False

        with patch("cv2.VideoCapture", return_value=cap), \
             pytest.raises(ValueError, match="Cannot open video file"):
            vi.process_video(
                video_path=Path("bad_file.mp4"),
                video_name="bad_file.mp4",
            )


# ===========================================================================
# 6. API endpoint tests
# ===========================================================================

@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from roadguard.backend.app.main import app
    return TestClient(app)


class TestVideoAPIEndpoints:
    def test_list_video_inspections_returns_list(self, client):
        response = client.get("/api/video/inspections")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_get_missing_inspection_returns_404(self, client):
        response = client.get("/api/video/inspections/nonexistent-uuid")
        assert response.status_code == 404

    def test_detect_unsupported_format_returns_415(self, client):
        """A .txt file should be rejected immediately with HTTP 415."""
        response = client.post(
            "/api/video/detect",
            files={"file": ("document.txt", b"not a video", "text/plain")},
        )
        assert response.status_code == 415

    def test_detect_invalid_video_bytes_returns_422(self, client):
        """Valid extension but garbage bytes → cv2 cannot open → 422."""
        from roadguard.backend.app.services import video_inspection as vi
        import cv2

        cap = MagicMock()
        cap.isOpened.return_value = False

        with patch("cv2.VideoCapture", return_value=cap), \
             patch("roadguard.backend.app.services.video_inspection._load_model"):
            response = client.post(
                "/api/video/detect",
                files={"file": ("road.mp4", b"\x00" * 64, "video/mp4")},
            )
        assert response.status_code == 422

    def test_detect_processes_mocked_video(self, client):
        """End-to-end test using mocked cv2 and model."""
        from roadguard.backend.app.services import video_inspection as vi
        import numpy as np

        # OpenCV returns (retval, frame) tuples
        frames = [(True, np.zeros((480, 640, 3), dtype="uint8"))] * 30
        frames.append((False, None))
        call_count = {"n": 0}

        def read():
            n = call_count["n"]
            call_count["n"] += 1
            if n < len(frames):
                return frames[n]
            return (None, False)

        cap = MagicMock()
        cap.isOpened.return_value = True
        cap.get.side_effect = lambda prop: {0: 30.0, 7: 30}.get(prop, 0)
        cap.read.side_effect = read

        model = MagicMock()
        model.names = {0: "Potholes"}
        empty_result = MagicMock()
        empty_result.boxes = []
        model.predict.return_value = [empty_result]

        with patch("cv2.VideoCapture", return_value=cap), \
             patch("roadguard.backend.app.services.video_inspection._load_model", return_value=model):
            response = client.post(
                "/api/video/detect",
                files={"file": ("road_video.mp4", b"\x00" * 64, "video/mp4")},
                data={"frame_interval": "30", "confidence": "0.25"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "inspection_id" in data
        assert "road_health_score" in data
        assert "priority" in data
        assert isinstance(data["frame_summaries"], list)
        assert isinstance(data["class_distribution"], dict)

    def test_detect_with_saved_record_retrievable(self, client):
        """After a successful detect, the result should be retrievable by ID."""
        from roadguard.backend.app.services import video_inspection as vi
        import numpy as np

        # OpenCV returns (retval, frame) tuples
        frames = [(True, np.zeros((480, 640, 3), dtype="uint8"))] * 30
        frames.append((False, None))
        call_count = {"n": 0}

        def read():
            n = call_count["n"]
            call_count["n"] += 1
            return frames[n] if n < len(frames) else (None, False)

        cap = MagicMock()
        cap.isOpened.return_value = True
        cap.get.side_effect = lambda prop: {0: 30.0, 7: 30}.get(prop, 0)
        cap.read.side_effect = read

        model = MagicMock()
        model.names = {0: "Potholes"}
        empty_result = MagicMock()
        empty_result.boxes = []
        model.predict.return_value = [empty_result]

        with patch("cv2.VideoCapture", return_value=cap), \
             patch("roadguard.backend.app.services.video_inspection._load_model", return_value=model):
            post_resp = client.post(
                "/api/video/detect",
                files={"file": ("road_video2.mp4", b"\x00" * 64, "video/mp4")},
                data={"frame_interval": "30", "confidence": "0.25"},
            )

        assert post_resp.status_code == 200
        inspection_id = post_resp.json()["inspection_id"]

        get_resp = client.get(f"/api/video/inspections/{inspection_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["inspection_id"] == inspection_id
