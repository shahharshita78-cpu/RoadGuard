"""
Synthetic road inspection dataset generator for Phase 12.

Generates realistic longitudinal inspection histories for multiple road segments
over multiple time periods. Features represent the state at the current inspection,
while the targets (future road health and high-priority maintenance indicator)
are derived strictly from the subsequent simulated inspection.
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path to reuse existing services
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from roadguard.backend.app.services.severity import compute_severity
from roadguard.backend.app.services.scoring import compute_road_health
from roadguard.backend.app.services.optimizer import compute_maintenance_priority

# Define default damage classes
DAMAGE_CLASSES = ["D00", "D10", "D20", "D40"]


def generate_detections(health: float, traffic_factor: float) -> list[dict]:
    """Generate a realistic set of detections based on current road health."""
    if health >= 90:
        count = random.choices([0, 1], weights=[0.8, 0.2])[0]
    elif health >= 75:
        count = random.randint(1, 2)
    elif health >= 50:
        count = random.randint(2, 5)
    else:
        count = random.randint(4, 10)

    detections = []
    for _ in range(count):
        # Choose class based on health (worse health -> more severe damage classes)
        if health >= 80:
            cls = random.choices(["D00", "D10"], weights=[0.7, 0.3])[0]
        elif health >= 60:
            cls = random.choices(["D00", "D10", "D20"], weights=[0.4, 0.4, 0.2])[0]
        else:
            cls = random.choices(DAMAGE_CLASSES, weights=[0.2, 0.3, 0.3, 0.2])[0]

        # Bounding box simulation
        x1 = random.randint(10, 300)
        y1 = random.randint(10, 200)
        x2 = x1 + random.randint(30, 200)
        y2 = y1 + random.randint(30, 200)
        
        # Confidence score
        conf = round(random.uniform(0.55, 0.95), 4)
        
        detections.append({
            "damage_class": cls,
            "confidence": conf,
            "bbox": {"x1": x1, "y1": y1, "x2": x2, "y2": y2}
        })
    return detections


def generate_longitudinal_data(num_roads: int, periods: int, seed: int = 42) -> list[dict]:
    """Generate simulated sequential inspection records for road segments."""
    random.seed(seed)
    dataset = []

    start_date = datetime(2025, 1, 1)

    for i in range(1, num_roads + 1):
        road_id = f"ROAD_{i:03d}"
        
        # Assign stable characteristics to the road segment
        traffic_factor = random.uniform(0.8, 2.0)  # heavier roads deteriorate faster
        base_deterioration_rate = random.uniform(0.05, 0.15)  # daily health reduction rate
        
        # Initial health status
        current_health = random.uniform(85, 100)
        current_date = start_date + timedelta(days=random.randint(0, 30))

        road_history = []

        for p in range(periods):
            # 1. Simulate detections for the current health state
            detections = generate_detections(current_health, traffic_factor)
            
            # Compute exact scores using existing services
            # Assume constant standard video/image frame resolution for area ratio calculation
            w, h = 1280, 720
            sev = compute_severity(detections, w, h)
            health_calc = compute_road_health(detections, w, h)
            prio = compute_maintenance_priority(
                sev["severity_score"],
                health_calc["road_health_score"],
                len(detections)
            )

            # Record current observation details
            obs = {
                "road_segment_id": road_id,
                "timestamp": current_date.isoformat(),
                "road_health_score": health_calc["road_health_score"],
                "severity_score": sev["severity_score"],
                "priority_score": prio["priority_score"],
                "priority": prio["priority"],
                "detection_count": len(detections),
                "damage_class_counts": json.dumps({
                    c: sum(1 for d in detections if d["damage_class"] == c) for c in DAMAGE_CLASSES
                }),
                "avg_confidence": round(sum(d["confidence"] for d in detections) / len(detections), 4) if detections else 0.0,
                "max_severity_score": max([d["confidence"] * 100 for d in detections]) if detections else 0.0,
                "damage_frame_pct": round(random.uniform(10, 80), 1) if len(detections) > 0 else 0.0,
                "unique_detections": len(detections),
                "maintenance_performed": 0,
            }
            road_history.append(obs)

            # 2. Advance time and simulate deterioration/maintenance for the next period
            time_gap_days = random.randint(30, 90)
            current_date += timedelta(days=time_gap_days)

            # Check for maintenance intervention
            # If priority score is critical/high, there is a chance it gets repaired
            maintenance_chance = 0.0
            if prio["priority_score"] >= 85:
                maintenance_chance = 0.75
            elif prio["priority_score"] >= 65:
                maintenance_chance = 0.40
            elif prio["priority_score"] >= 40:
                maintenance_chance = 0.15

            if random.random() < maintenance_chance:
                # Reset health to excellent
                current_health = random.uniform(92, 100)
                obs["maintenance_performed"] = 1
            else:
                # Normal deterioration progress
                deterioration = base_deterioration_rate * traffic_factor * time_gap_days
                current_health = max(0.0, current_health - deterioration)

        # 3. Create training targets by linking current features to the subsequent observation
        for idx in range(len(road_history)):
            curr = road_history[idx]
            
            # Next observation details
            if idx < len(road_history) - 1:
                nxt = road_history[idx + 1]
                curr["future_road_health"] = nxt["road_health_score"]
                # Define primary binary target: does it cross the priority threshold? (default 65)
                # We will record both the future priority score and build the target indicator
                curr["future_priority_score"] = nxt["priority_score"]
                curr["days_to_next_inspection"] = (datetime.fromisoformat(nxt["timestamp"]) - datetime.fromisoformat(curr["timestamp"])).days
            else:
                curr["future_road_health"] = None
                curr["future_priority_score"] = None
                curr["days_to_next_inspection"] = None

            # Calculate helper retrospective features based on past observations
            if idx > 0:
                prev = road_history[idx - 1]
                gap = (datetime.fromisoformat(curr["timestamp"]) - datetime.fromisoformat(prev["timestamp"])).days
                curr["days_since_previous_inspection"] = gap
                curr["previous_road_health_score"] = prev["road_health_score"]
                # Change rate per day
                health_change = prev["road_health_score"] - curr["road_health_score"]
                curr["deterioration_rate"] = round(health_change / max(1, gap), 4)
                curr["number_of_previous_inspections"] = idx
            else:
                curr["days_since_previous_inspection"] = 0
                curr["previous_road_health_score"] = curr["road_health_score"]
                curr["deterioration_rate"] = 0.0
                curr["number_of_previous_inspections"] = 0

            dataset.append(curr)

    return dataset


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic longitudinal road deterioration data.")
    parser.add_argument("--roads", type=int, default=50, help="Number of distinct road segments")
    parser.add_argument("--periods", type=int, default=8, help="Number of inspection periods per road")
    parser.add_argument("--output", type=str, default="data/synthetic_inspections.csv", help="Output file path")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Generating data for {args.roads} roads over {args.periods} periods (seed={args.seed})...")
    data = generate_longitudinal_data(args.roads, args.periods, args.seed)

    if not data:
        print("Error: No data generated.")
        sys.exit(1)

    headers = list(data[0].keys())

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(data)

    print(f"Dataset saved to {output_path}")
    print(f"Total records: {len(data)}")


if __name__ == "__main__":
    main()
