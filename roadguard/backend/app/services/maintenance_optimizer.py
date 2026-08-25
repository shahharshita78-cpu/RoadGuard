"""
Maintenance Optimizer Service (Phase 13).

Uses Google OR-Tools to solve a binary integer programming (Knapsack) problem:
Selecting the optimal set of road segments for repair under a fixed budget.
Provides deterministic cost, benefit models, persistence, and explainable reasons.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from ortools.linear_solver import pywraplp

# Database file path same as other services
from .db_path import DB_PATH


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_optimization_schema() -> None:
    """Create the maintenance_optimizations table if it does not exist."""
    conn = _get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS maintenance_optimizations (
            id                      INTEGER PRIMARY KEY AUTOINCREMENT,
            optimization_id         TEXT UNIQUE NOT NULL,
            timestamp               TEXT NOT NULL,
            budget                  REAL NOT NULL,
            allocated_budget        REAL NOT NULL,
            remaining_budget        REAL NOT NULL,
            total_expected_benefit  REAL NOT NULL,
            estimated_health_improvement REAL NOT NULL,
            estimated_risk_reduction     REAL NOT NULL,
            selected_count          INTEGER NOT NULL,
            candidate_count         INTEGER NOT NULL,
            solver_status           TEXT NOT NULL,
            result_json             TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def save_optimization(record: dict) -> dict:
    """Save an optimization run results to database."""
    ensure_optimization_schema()
    conn = _get_connection()
    conn.execute(
        """
        INSERT INTO maintenance_optimizations (
            optimization_id, timestamp, budget, allocated_budget,
            remaining_budget, total_expected_benefit, estimated_health_improvement,
            estimated_risk_reduction, selected_count, candidate_count,
            solver_status, result_json
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            record["optimization_id"],
            record["timestamp"],
            record["budget"],
            record["allocated_budget"],
            record["remaining_budget"],
            record["total_expected_benefit"],
            record["estimated_health_improvement"],
            record["estimated_risk_reduction"],
            record["selected_count"],
            record["candidate_count"],
            record["solver_status"],
            json.dumps(record),  # Store full dict in result_json
        ),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM maintenance_optimizations WHERE optimization_id = ?",
        (record["optimization_id"],),
    ).fetchone()
    conn.close()
    return _deserialise_optimization(dict(row))


def get_latest_optimization() -> Optional[dict]:
    """Retrieve the most recent optimization run result, or None."""
    ensure_optimization_schema()
    conn = _get_connection()
    row = conn.execute(
        "SELECT * FROM maintenance_optimizations ORDER BY timestamp DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return _deserialise_optimization(dict(row)) if row else None


def _deserialise_optimization(row: dict) -> dict:
    """Parse the JSON result field back to Python object."""
    raw = row.get("result_json")
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            pass
    return row


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

def calculate_repair_cost(
    road_health_score: float,
    severity_score: float,
    detection_count: int,
    damage_class_counts: dict
) -> float:
    """
    Transparent, deterministic cost model for road repairs.
    
    Formula:
      Base cost: 5000.0 (mobilisation/fixed cost)
      Defect density cost: 1200.0 per defect count
      Severity penalty: 80.0 per severity score point
      Deterioration state penalty: 60.0 per (100 - health_score)
      Specific defect surcharge:
        - 2500.0 per D40 (pothole)
        - 1500.0 per D20 (alligator crack)
    """
    base_cost = 5000.0
    defect_cost = 1200.0 * max(0, detection_count)
    severity_cost = 80.0 * max(0.0, severity_score)
    degradation_cost = 60.0 * max(0.0, 100.0 - road_health_score)
    
    pothole_count = damage_class_counts.get("D40", 0)
    alligator_count = damage_class_counts.get("D20", 0)
    defect_surcharges = (2500.0 * max(0, pothole_count)) + (1500.0 * max(0, alligator_count))
    
    total = base_cost + defect_cost + severity_cost + degradation_cost + defect_surcharges
    return round(total, 2)


def calculate_benefit(
    road_health_score: float,
    priority_score: float,
    deterioration_risk: float,
    predicted_future_health: float,
    severity_score: float,
    avg_confidence: float
) -> float:
    """
    Explainable maintenance benefit model.
    Rewards segments with low current health, high priority, and high deterioration risks
    while avoiding excessive double-counting.
    """
    # Low health factor
    health_factor = (100.0 - max(0.0, min(100.0, road_health_score))) * 0.30
    
    # Priority rank factor
    priority_factor = max(0.0, min(100.0, priority_score)) * 0.25
    
    # Predicted deterioration risk factor
    risk_factor = max(0.0, min(1.0, deterioration_risk)) * 100.0 * 0.25
    
    # Predicted health decline factor (current - future)
    decline = max(0.0, road_health_score - predicted_future_health)
    decline_factor = decline * 0.10
    
    # Severity and detection confidence (smaller weights)
    severity_factor = max(0.0, min(100.0, severity_score)) * 0.05
    confidence_factor = max(0.0, min(1.0, avg_confidence)) * 100.0 * 0.05
    
    total = health_factor + priority_factor + risk_factor + decline_factor + severity_factor + confidence_factor
    return round(total, 2)


def generate_explainability_reasons(
    cand: dict,
    cost: float,
    benefit: float,
    selected: bool,
    is_budget_limited: bool = False
) -> List[str]:
    """Generate professional, fact-based reasons for optimizer decisions."""
    reasons = []
    
    health = cand["road_health_score"]
    priority = cand["priority_score"]
    risk = cand["deterioration_risk"]
    future_health = cand["predicted_future_health"]
    defects = cand["detection_count"]

    if selected:
        if health < 50:
            reasons.append(f"Critical road surface health index ({int(health)}/100)")
        elif health < 70:
            reasons.append(f"Moderate road health degradation ({int(health)}/100)")
            
        if priority >= 65:
            reasons.append(f"High maintenance priority urgency classification ({int(priority)})")
            
        if risk >= 0.50:
            reasons.append(f"High predicted deterioration risk ({int(risk * 100)}%)")
            
        if health - future_health >= 10.0:
            reasons.append(f"Significant predicted health decline ({int(health - future_health)} points)")
            
        if defects >= 5:
            reasons.append(f"High density of surface defects ({defects} counts)")
            
        if not reasons:
            reasons.append("Optimal cost-to-benefit ratio within requested budget")
    else:
        if is_budget_limited:
            reasons.append(f"Excluded due to budget constraints (estimated repair cost: {cost:,.2f})")
        else:
            if health >= 85:
                reasons.append("Segment is currently in excellent condition")
            if priority < 40:
                reasons.append("Low maintenance urgency level")
            if risk < 0.20:
                reasons.append("Low predicted risk of further degradation")
                
            if not reasons:
                reasons.append("Low overall repair benefit score relative to cost")
                
    return reasons


# ---------------------------------------------------------------------------
# Core Solver
# ---------------------------------------------------------------------------

def optimize_maintenance_plan(
    candidates: List[dict],
    budget: float
) -> dict:
    """
    Solves the budget-constrained maintenance optimization using OR-Tools MIP solver.
    """
    if budget <= 0:
        raise ValueError("Budget must be a positive number greater than 0.")
        
    if not candidates:
        return {
            "optimization_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "budget": budget,
            "allocated_budget": 0.0,
            "remaining_budget": budget,
            "total_expected_benefit": 0.0,
            "estimated_health_improvement": 0.0,
            "estimated_risk_reduction": 0.0,
            "selected_count": 0,
            "candidate_count": 0,
            "solver_status": "EMPTY",
            "selected_segments": [],
            "unselected_segments": [],
        }

    # 1. Clean, preprocess, and calculate costs/benefits for each candidate
    prepped_candidates = []
    seen_ids = set()

    for item in candidates:
        segment_id = item.get("road_segment_id") or item.get("segment_id")
        if not segment_id:
            raise ValueError("Candidate segment must specify a segment identifier ('road_segment_id').")
        
        if segment_id in seen_ids:
            # Skip duplicate segment IDs to avoid solver redundancy
            continue
        seen_ids.add(segment_id)

        # Handle fallbacks for missing prediction/health values
        road_health_score = item.get("road_health_score")
        if road_health_score is None:
            # Check for alternative key
            road_health_score = item.get("current_health", 100.0)
        
        severity_score = item.get("severity_score", 0.0)
        priority_score = item.get("priority_score", 0.0)
        detection_count = item.get("detection_count", 0)
        damage_class_counts = item.get("damage_class_counts", {})
        if isinstance(damage_class_counts, str):
            try:
                damage_class_counts = json.loads(damage_class_counts)
            except Exception:
                damage_class_counts = {}

        # Fallbacks for Phase 12 predictive values if not provided
        deterioration_risk = item.get("deterioration_risk")
        if deterioration_risk is None:
            # Fallback
            deterioration_risk = item.get("risk_probability", 0.10)
            
        predicted_future_health = item.get("predicted_future_health")
        if predicted_future_health is None:
            # Fallback
            predicted_future_health = max(0.0, road_health_score - 5.0)

        # Average confidence fallback
        avg_confidence = item.get("avg_confidence", 0.8)

        # Calculate cost and benefit deterministically
        cost = calculate_repair_cost(road_health_score, severity_score, detection_count, damage_class_counts)
        benefit = calculate_benefit(
            road_health_score, priority_score, deterioration_risk,
            predicted_future_health, severity_score, avg_confidence
        )

        if cost <= 0:
            # Invalid cost filter
            continue

        prepped_candidates.append({
            "road_segment_id": segment_id,
            "road_health_score": float(road_health_score),
            "severity_score": float(severity_score),
            "priority_score": float(priority_score),
            "detection_count": int(detection_count),
            "damage_class_counts": damage_class_counts,
            "deterioration_risk": float(deterioration_risk),
            "predicted_future_health": float(predicted_future_health),
            "avg_confidence": float(avg_confidence),
            "estimated_cost": cost,
            "benefit_score": benefit
        })

    if not prepped_candidates:
        raise ValueError("No valid candidates with positive costs found.")

    # 2. Build the Mixed-Integer Programming solver
    # We use SCIP or falls back to SAT (BOP)
    solver = pywraplp.Solver.CreateSolver("SCIP")
    if not solver:
        # Fallback
        solver = pywraplp.Solver.CreateSolver("SAT")
    
    if not solver:
        raise RuntimeError("Could not create OR-Tools solver instance.")

    # Decision variables: x[i] is 1 if prepped_candidates[i] is selected, 0 otherwise
    n = len(prepped_candidates)
    x = [solver.IntVar(0, 1, f"x_{i}") for i in range(n)]

    # Constraint: Sum(cost[i] * x[i]) <= budget
    budget_constraint = solver.Constraint(0, budget, "budget_limit")
    for i in range(n):
        budget_constraint.SetCoefficient(x[i], prepped_candidates[i]["estimated_cost"])

    # Objective: Maximize Sum(benefit[i] * x[i])
    objective = solver.Objective()
    for i in range(n):
        objective.SetCoefficient(x[i], prepped_candidates[i]["benefit_score"])
    objective.SetMaximization()

    # 3. Solve the optimization
    status = solver.Solve()

    selected_indices = []
    unselected_indices = []

    if status == pywraplp.Solver.OPTIMAL or status == pywraplp.Solver.FEASIBLE:
        solver_status_str = "OPTIMAL" if status == pywraplp.Solver.OPTIMAL else "FEASIBLE"
        for i in range(n):
            if x[i].solution_value() > 0.5:
                selected_indices.append(i)
            else:
                unselected_indices.append(i)
    else:
        solver_status_str = "INFEASIBLE"
        # If infeasible or error, select none
        unselected_indices = list(range(n))

    # 4. Compile outcomes, metrics, and explanations
    selected_segments = []
    allocated_budget = 0.0
    total_benefit = 0.0
    
    # Cumulative health improvement: Sum((100 - health) * selected_i) / count
    total_health_deficiency_repaired = 0.0
    # Cumulative risk reduction: Sum(risk * selected_i) / count
    total_risk_reduced = 0.0

    for idx in selected_indices:
        cand = prepped_candidates[idx]
        allocated_budget += cand["estimated_cost"]
        total_benefit += cand["benefit_score"]
        total_health_deficiency_repaired += (100.0 - cand["road_health_score"])
        total_risk_reduced += cand["deterioration_risk"]

        reasons = generate_explainability_reasons(cand, cand["estimated_cost"], cand["benefit_score"], selected=True)
        
        selected_segments.append({
            "segment_id": cand["road_segment_id"],
            "estimated_cost": cand["estimated_cost"],
            "benefit_score": cand["benefit_score"],
            "current_health": cand["road_health_score"],
            "predicted_future_health": cand["predicted_future_health"],
            "deterioration_risk": cand["deterioration_risk"],
            "maintenance_priority": cand["priority_score"],
            "reasons": reasons
        })

    # Sort selected segments by benefit-to-cost ratio descending (priority ranking)
    selected_segments = sorted(
        selected_segments,
        key=lambda s: s["benefit_score"] / max(1.0, s["estimated_cost"]),
        reverse=True
    )

    unselected_segments = []
    for idx in unselected_indices:
        cand = prepped_candidates[idx]
        # Determine if budget constraints prevented its selection
        # (It would have been selected if budget was infinite)
        is_budget_limited = cand["estimated_cost"] > (budget - allocated_budget)
        
        reasons = generate_explainability_reasons(
            cand, cand["estimated_cost"], cand["benefit_score"],
            selected=False, is_budget_limited=is_budget_limited
        )
        
        unselected_segments.append({
            "segment_id": cand["road_segment_id"],
            "estimated_cost": cand["estimated_cost"],
            "benefit_score": cand["benefit_score"],
            "current_health": cand["road_health_score"],
            "predicted_future_health": cand["predicted_future_health"],
            "deterioration_risk": cand["deterioration_risk"],
            "maintenance_priority": cand["priority_score"],
            "reasons": reasons
        })

    # Validation Checks
    allocated_budget = round(allocated_budget, 2)
    remaining_budget = round(budget - allocated_budget, 2)
    
    # Validation constraint assert checks
    if allocated_budget > budget:
        raise RuntimeError("Solver allocation error: allocated budget exceeds limits.")

    # Calculate average improvements
    num_selected = len(selected_segments)
    est_health_imp = round(total_health_deficiency_repaired / num_selected, 1) if num_selected > 0 else 0.0
    est_risk_red = round((total_risk_reduced / num_selected) * 100.0, 1) if num_selected > 0 else 0.0

    return {
        "optimization_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": solver_status_str,
        "budget": budget,
        "allocated_budget": allocated_budget,
        "remaining_budget": remaining_budget,
        "total_expected_benefit": round(total_benefit, 2),
        "estimated_health_improvement": est_health_imp,
        "estimated_risk_reduction": est_risk_red,
        "selected_count": num_selected,
        "candidate_count": len(prepped_candidates),
        "solver_status": solver_status_str,
        "selected_segments": selected_segments,
        "unselected_segments": unselected_segments,
        "method": "OR-Tools"
    }
