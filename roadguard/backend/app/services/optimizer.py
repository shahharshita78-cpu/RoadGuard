"""
Maintenance priority scoring service.

Computes an explainable maintenance priority score (0–100) from:
  - severity_score (0–100): higher severity → higher urgency
  - road_health_score (0–100): lower health → higher urgency
  - detection_count: more defects → higher urgency

Formula:
    degradation   = 100 - road_health_score     # [0..100]
    density_bonus = min(20, detection_count * 5) # up to 20 pts
    raw           = (severity_score * 0.5) + (degradation * 0.4) + density_bonus
    priority_score = clamp(round(raw), 0, 100)

Priority thresholds:
    [85, 100] → Immediate
    [65,  84] → High
    [40,  64] → Medium
    [ 0,  39] → Routine
"""
from __future__ import annotations

from typing import List


PRIORITY_THRESHOLDS = [
    (85, "Immediate"),
    (65, "High"),
    (40, "Medium"),
    (0,  "Routine"),
]


def compute_maintenance_priority(
    severity_score: int,
    road_health_score: int,
    detection_count: int,
) -> dict:
    """
    Compute maintenance priority score, label, and human-readable reasons.

    Args:
        severity_score: integer 0–100 from the severity engine
        road_health_score: integer 0–100 from the road health index
        detection_count: number of individual defects detected

    Returns:
        {"priority_score": int, "priority": str, "reasons": [str, ...]}
    """
    degradation = 100 - road_health_score
    density_bonus = min(20.0, detection_count * 5.0)
    raw = (severity_score * 0.5) + (degradation * 0.4) + density_bonus
    priority_score = int(round(max(0.0, min(100.0, raw))))

    label = "Routine"
    for threshold, name in PRIORITY_THRESHOLDS:
        if priority_score >= threshold:
            label = name
            break

    reasons: List[str] = []
    if severity_score >= 65:
        reasons.append("High severity damage detected")
    elif severity_score >= 35:
        reasons.append("Moderate severity damage detected")
    if road_health_score < 30:
        reasons.append("Road surface in critical condition")
    elif road_health_score < 50:
        reasons.append("Road health below acceptable threshold")
    if detection_count >= 5:
        reasons.append(f"High defect density ({detection_count} defects in frame)")
    elif detection_count >= 3:
        reasons.append(f"Multiple defects detected ({detection_count})")
    if not reasons:
        reasons.append("No immediate maintenance concerns identified")

    return {
        "priority_score": priority_score,
        "priority": label,
        "reasons": reasons,
    }
