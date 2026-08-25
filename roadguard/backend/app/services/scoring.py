"""
Road Health Index (RHI) scoring service.

The Road Health Index is a project-defined analytical index in the range
[0, 100] where 100 represents a perfectly healthy road surface with no
detected defects, and 0 represents a severely degraded surface.

Formula:
    base_penalty = sum(class_weight_i * confidence_i * area_ratio_i)
                   for every detection i
    density_penalty = min(20, detection_count * 4)
    raw_health = 100 - (base_penalty * 60) - density_penalty
    rhi = clamp(round(raw_health), 0, 100)

Condition thresholds (configurable):
    [85, 100] → Excellent
    [70,  84] → Good
    [50,  69] → Moderate
    [30,  49] → Poor
    [ 0,  29] → Critical
"""
from __future__ import annotations

from typing import List

from .severity import CLASS_WEIGHTS, DEFAULT_CLASS_WEIGHT

CONDITION_THRESHOLDS = [
    (85, "Excellent"),
    (70, "Good"),
    (50, "Moderate"),
    (30, "Poor"),
    (0,  "Critical"),
]


def compute_road_health(
    detections: List[dict],
    image_width: int,
    image_height: int,
) -> dict:
    """
    Compute Road Health Index and condition label from a list of detections.

    Args:
        detections: list of detection dicts (damage_class, confidence, bbox)
        image_width: pixel width of the source image
        image_height: pixel height of the source image

    Returns:
        {"road_health_score": int, "road_condition": str}
    """
    if not detections:
        return {"road_health_score": 100, "road_condition": "Excellent"}

    image_area = max(1, image_width * image_height)
    base_penalty = 0.0

    for d in detections:
        weight = CLASS_WEIGHTS.get(d["damage_class"], DEFAULT_CLASS_WEIGHT)
        conf = d["confidence"]
        bbox = d["bbox"]
        w = max(0, bbox["x2"] - bbox["x1"])
        h = max(0, bbox["y2"] - bbox["y1"])
        area_ratio = min(1.0, (w * h) / image_area)
        base_penalty += weight * conf * area_ratio

    density_penalty = min(20.0, len(detections) * 4.0)
    raw_health = 100.0 - (base_penalty * 60.0) - density_penalty
    rhi = int(round(max(0.0, min(100.0, raw_health))))

    condition = "Critical"
    for threshold, label in CONDITION_THRESHOLDS:
        if rhi >= threshold:
            condition = label
            break

    return {"road_health_score": rhi, "road_condition": condition}
