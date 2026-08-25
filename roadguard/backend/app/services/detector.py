"""
YOLO-based road damage detection service.

Wraps the Ultralytics YOLO model to produce structured detections
containing class label, confidence, and bounding-box coordinates.
The model is loaded once at application start-up and reused across requests.
"""
from __future__ import annotations

import io
from pathlib import Path
from typing import List, Tuple

from PIL import Image

MODEL_PATH = Path(__file__).parents[4] / "models" / "road_damage.pt"

# Lazy-loaded singleton
_model = None


def _load_model():
    """Load the YOLO model from disk on first call."""
    global _model
    if _model is None:
        from ultralytics import YOLO
        _model = YOLO(str(MODEL_PATH))
    return _model


def is_model_available() -> bool:
    """Return True if the trained weights file exists on disk."""
    return MODEL_PATH.exists()


def run_inference(
    image_bytes: bytes,
    confidence_threshold: float = 0.25,
) -> Tuple[List[dict], int, int]:
    """
    Run YOLO inference on raw image bytes.

    Returns:
        detections: list of dicts with keys damage_class, confidence, bbox
        image_width: pixel width of the input image
        image_height: pixel height of the input image
    """
    model = _load_model()
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    image_width, image_height = img.size

    results = model.predict(source=img, conf=confidence_threshold, verbose=False)

    detections: List[dict] = []
    for result in results:
        for box in result.boxes:
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            x1, y1, x2, y2 = (int(v) for v in box.xyxy[0].tolist())
            detections.append(
                {
                    "damage_class": model.names[cls_id],
                    "confidence": round(conf, 4),
                    "bbox": {"x1": x1, "y1": y1, "x2": x2, "y2": y2},
                }
            )

    return detections, image_width, image_height
