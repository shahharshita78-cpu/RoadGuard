"""
Severity scoring service.

Computes a severity score (0–100) from YOLO detection results using three
measurable factors:

  1. Damage class weight  — heavier damage types score higher.
  2. Bounding-box area ratio — fraction of the image area the defect covers.
  3. Detector confidence — higher confidence increases the score.

Formula (per detection):
    raw = (class_weight * 40) + (bbox_area_ratio * 40) + (confidence * 20)

The maximum per-detection score is 100. When multiple detections are present
the final score is the mean of the top-3 scores (or all if fewer than 3),
clamped to [0, 100].

Thresholds:
    [0,  34]  → Low
    [35, 64]  → Medium
    [65, 100] → High
"""
from __future__ import annotations

from typing import List

# Relative severity weights per damage class (RDD2020 taxonomy).
# D00: longitudinal crack (least severe)
# D10: transverse crack
# D20: alligator crack
# D40: pothole (most severe)
CLASS_WEIGHTS = {
    "D00": 0.25,
    "D10": 0.40,
    "D20": 0.60,
    "D40": 1.00,
}
DEFAULT_CLASS_WEIGHT = 0.50

SEVERITY_THRESHOLDS = [
    (65, "High"),
    (35, "Medium"),
    (0,  "Low"),
]


def _score_detection(
    damage_class: str,
    confidence: float,
    bbox: dict,
    image_width: int,
    image_height: int,
) -> float:
    """Return a raw severity score (0–100) for a single detection."""
    class_weight = CLASS_WEIGHTS.get(damage_class, DEFAULT_CLASS_WEIGHT)

    bbox_w = max(0, bbox["x2"] - bbox["x1"])
    bbox_h = max(0, bbox["y2"] - bbox["y1"])
    image_area = max(1, image_width * image_height)
    bbox_area_ratio = min(1.0, (bbox_w * bbox_h) / image_area)

    raw = (class_weight * 40.0) + (bbox_area_ratio * 40.0) + (confidence * 20.0)
    return min(100.0, raw)


def compute_severity(
    detections: List[dict],
    image_width: int,
    image_height: int,
) -> dict:
    """
    Compute aggregate severity score and label from a list of detections.

    Args:
        detections: list of detection dicts (damage_class, confidence, bbox)
        image_width: pixel width of the source image
        image_height: pixel height of the source image

    Returns:
        {"severity_score": int, "severity": str}
    """
    if not detections:
        return {"severity_score": 0, "severity": "Low"}

    scores = [
        _score_detection(
            d["damage_class"],
            d["confidence"],
            d["bbox"],
            image_width,
            image_height,
        )
        for d in detections
    ]

    # Use mean of top-3 detections so many small cracks don't dominate.
    top_scores = sorted(scores, reverse=True)[:3]
    aggregate = sum(top_scores) / len(top_scores)
    final_score = int(round(min(100.0, aggregate)))

    label = "Low"
    for threshold, name in SEVERITY_THRESHOLDS:
        if final_score >= threshold:
            label = name
            break

    return {"severity_score": final_score, "severity": label}
