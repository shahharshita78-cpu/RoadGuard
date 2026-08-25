"""
Unit and integration tests for Phase 13: Budget-Constrained Maintenance Optimization.
Validates deterministic cost/benefit formulas, solver knapsack constraints,
persistence, explainability reason generation, and API router.
Exercises the actual Google OR-Tools solver (no mocking of the solver itself).
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Ensure project root importable
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from roadguard.backend.app.services.maintenance_optimizer import (
    calculate_repair_cost,
    calculate_benefit,
    optimize_maintenance_plan,
    save_optimization,
    get_latest_optimization
)


@pytest.fixture
def sample_candidates() -> list[dict]:
    """Return a standard list of 4 candidates with distinct costs and benefits."""
    return [
        {
            "road_segment_id": "SEG_001",
            "road_health_score": 60.0,
            "severity_score": 40.0,
            "priority_score": 70.0,
            "detection_count": 3,
            "damage_class_counts": json.dumps({"D20": 1, "D40": 0}),
            "deterioration_risk": 0.45,
            "predicted_future_health": 55.0,
            "avg_confidence": 0.85
        },
        {
            "road_segment_id": "SEG_002",
            "road_health_score": 45.0,
            "severity_score": 65.0,
            "priority_score": 85.0,
            "detection_count": 6,
            "damage_class_counts": json.dumps({"D40": 2}),
            "deterioration_risk": 0.80,
            "predicted_future_health": 30.0,
            "avg_confidence": 0.90
        },
        {
            "road_segment_id": "SEG_003",
            "road_health_score": 85.0,
            "severity_score": 15.0,
            "priority_score": 30.0,
            "detection_count": 1,
            "damage_class_counts": json.dumps({"D00": 1}),
            "deterioration_risk": 0.15,
            "predicted_future_health": 80.0,
            "avg_confidence": 0.70
        },
        {
            "road_segment_id": "SEG_004",
            "road_health_score": 75.0,
            "severity_score": 25.0,
            "priority_score": 45.0,
            "detection_count": 2,
            "damage_class_counts": json.dumps({"D10": 1}),
            "deterioration_risk": 0.30,
            "predicted_future_health": 70.0,
            "avg_confidence": 0.80
        }
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestMaintenanceOptimizer:

    def test_optimizer_imports_and_instantiates(self):
        """1. Validate OR-Tools package is available and imports correctly."""
        from ortools.linear_solver import pywraplp
        solver = pywraplp.Solver.CreateSolver("SCIP")
        if not solver:
            solver = pywraplp.Solver.CreateSolver("SAT")
        assert solver is not None

    def test_deterministic_cost_calculation(self):
        """2. Validate cost model behaves deterministically."""
        # Cost parameters: health=80, severity=20, count=2, damages={"D40": 1, "D20": 0}
        cost1 = calculate_repair_cost(80.0, 20.0, 2, {"D40": 1, "D20": 0})
        cost2 = calculate_repair_cost(80.0, 20.0, 2, {"D40": 1, "D20": 0})
        
        # Base: 5000 + 2*1200 (2400) + 20*80 (1600) + (100-80)*60 (1200) + 2500 (pothole) = 12700.00
        assert cost1 == 12700.00
        assert cost1 == cost2

    def test_benefit_calculation(self):
        """3. Validate benefit formula calculations are correct."""
        benefit = calculate_benefit(
            road_health_score=60.0,
            priority_score=70.0,
            deterioration_risk=0.50,
            predicted_future_health=50.0,
            severity_score=40.0,
            avg_confidence=0.85
        )
        # Expected:
        # health: (100 - 60) * 0.3 = 12.0
        # priority: 70 * 0.25 = 17.5
        # risk: 0.5 * 100 * 0.25 = 12.5
        # decline: (60 - 50) * 0.1 = 1.0
        # severity: 40 * 0.05 = 2.0
        # confidence: 0.85 * 100 * 0.05 = 4.25
        # Total: 12 + 17.5 + 12.5 + 1.0 + 2.0 + 4.25 = 49.25
        assert benefit == 49.25

    def test_empty_candidate_list(self):
        """4. Validate empty candidate list resolves safely without crashes."""
        result = optimize_maintenance_plan([], budget=50000.0)
        assert result["solver_status"] == "EMPTY"
        assert result["selected_count"] == 0
        assert result["allocated_budget"] == 0.0

    def test_invalid_budget_handling(self, sample_candidates):
        """5. Validate zero/negative budget input raises ValueError."""
        with pytest.raises(ValueError, match="positive number"):
            optimize_maintenance_plan(sample_candidates, budget=0)
        with pytest.raises(ValueError, match="positive number"):
            optimize_maintenance_plan(sample_candidates, budget=-1000)

    def test_budget_smaller_than_all_candidate_costs(self, sample_candidates):
        """6. Validate solver selects nothing when budget is too small."""
        # Calculate minimum candidate cost
        costs = [calculate_repair_cost(
            c["road_health_score"], c["severity_score"], c["detection_count"],
            json.loads(c["damage_class_counts"])
        ) for c in sample_candidates]
        min_cost = min(costs)
        
        # Set budget to min_cost - 1000
        result = optimize_maintenance_plan(sample_candidates, budget=min_cost - 1000)
        assert result["selected_count"] == 0
        assert result["allocated_budget"] == 0.0
        assert len(result["unselected_segments"]) == len(sample_candidates)

    def test_sufficient_budget(self, sample_candidates):
        """7. Validate solver selects all candidates when budget is large enough."""
        result = optimize_maintenance_plan(sample_candidates, budget=1000000.0)
        assert result["selected_count"] == len(sample_candidates)
        assert result["remaining_budget"] >= 0.0

    def test_exact_budget_match(self):
        """8. Validate exact budget allocation constraints."""
        cand = [
            {
                "road_segment_id": "SEG_001",
                "road_health_score": 100.0, # cost = 5000
                "severity_score": 0.0,
                "priority_score": 50.0,
                "detection_count": 0,
            }
        ]
        result = optimize_maintenance_plan(cand, budget=5000.0)
        assert result["selected_count"] == 1
        assert result["allocated_budget"] == 5000.0
        assert result["remaining_budget"] == 0.0

    def test_knapsack_multiple_candidates_selection(self, sample_candidates):
        """9. Validate binary integer solver handles multiple candidates under constraint."""
        # Set budget to intermediate value that forces choice
        # SEG_002 is worst (highest priority/benefit), cost is high
        # SEG_001 has good benefit-to-cost
        result = optimize_maintenance_plan(sample_candidates, budget=30000.0)
        
        # Verify total cost <= budget
        assert result["allocated_budget"] <= 30000.0
        assert result["status"] == "OPTIMAL"
        
        # Selected segments should be populated
        assert len(result["selected_segments"]) > 0
        assert len(result["unselected_segments"]) > 0

    def test_selected_candidates_stay_within_budget(self, sample_candidates):
        """10. Validate that selected costs never exceed requesting budget limit."""
        import random
        random.seed(42)
        
        for _ in range(5):
            rand_budget = random.uniform(15000, 100000)
            result = optimize_maintenance_plan(sample_candidates, rand_budget)
            assert result["allocated_budget"] <= rand_budget

    def test_candidate_ranking(self, sample_candidates):
        """11. Validate selected segment output ranking is sorted by benefit-to-cost ratio."""
        result = optimize_maintenance_plan(sample_candidates, budget=100000.0)
        selected = result["selected_segments"]
        
        ratios = [s["benefit_score"] / s["estimated_cost"] for s in selected]
        # Should be sorted descending
        assert ratios == sorted(ratios, reverse=True)

    def test_invalid_candidate_handling(self):
        """12. Validate invalid inputs throw ValueErrors."""
        # Missing segment ID
        invalid_cand = [{"road_health_score": 80.0}]
        with pytest.raises(ValueError, match="segment identifier"):
            optimize_maintenance_plan(invalid_cand, budget=50000)
            
        # Duplicate segment IDs should be ignored/deduplicated (no crash)
        dups = [
            {"road_segment_id": "SEG_001", "road_health_score": 80.0},
            {"road_segment_id": "SEG_001", "road_health_score": 70.0}
        ]
        result = optimize_maintenance_plan(dups, budget=50000)
        # Deduplicated to 1 candidate
        assert result["candidate_count"] == 1

    def test_fallback_when_prediction_data_unavailable(self):
        """13. Validate fallbacks populate correct values when prediction is missing."""
        cand = [
            {
                "road_segment_id": "SEG_NO_PRED",
                "road_health_score": 80.0,
                "priority_score": 50.0,
                "detection_count": 1,
            }
        ]
        # Run prediction
        result = optimize_maintenance_plan(cand, budget=50000)
        selected = result["selected_segments"][0]
        # Fallbacks:
        # risk default to 0.10
        # future health default to 80.0 - 5.0 = 75.0
        assert selected["deterioration_risk"] == 0.10
        assert selected["predicted_future_health"] == 75.0

    def test_persistence_integration(self):
        """14. Validate database persistence insertions and latest run retrieval."""
        from datetime import datetime, timezone
        opt_id = f"opt-run-{uuid.uuid4()}"
        record = {
            "optimization_id": opt_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "budget": 50000.0,
            "allocated_budget": 24000.0,
            "remaining_budget": 26000.0,
            "total_expected_benefit": 85.5,
            "estimated_health_improvement": 20.0,
            "estimated_risk_reduction": 15.0,
            "selected_count": 2,
            "candidate_count": 5,
            "solver_status": "OPTIMAL",
            "selected_segments": [{"segment_id": "SEG_001", "estimated_cost": 12000.0}],
            "unselected_segments": []
        }
        
        saved = save_optimization(record)
        assert saved["optimization_id"] == opt_id
        
        latest = get_latest_optimization()
        assert latest is not None
        assert latest["optimization_id"] == opt_id
        assert latest["budget"] == 50000.0


# ---------------------------------------------------------------------------
# API Integration
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from roadguard.backend.app.main import app
    return TestClient(app)


class TestOptimizationAPI:

    def test_optimize_endpoint_with_custom_candidates(self, client, sample_candidates):
        """15. Validate /api/maintenance/optimize POST with custom candidates."""
        # Convert JSON strings to dict for API payload matching SegmentCandidate
        prepped = []
        for c in sample_candidates:
            copied = c.copy()
            copied["damage_class_counts"] = json.loads(copied["damage_class_counts"])
            prepped.append(copied)
            
        payload = {
            "budget": 30000.0,
            "road_segments": prepped
        }
        
        response = client.post("/api/maintenance/optimize", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "optimization_id" in data
        assert data["solver_status"] == "OPTIMAL"
        assert "selected_segments" in data

    def test_latest_optimization_endpoint(self, client):
        """16. Validate /api/maintenance/optimization/latest GET retrieval."""
        from datetime import datetime, timezone
        opt_id = f"opt-run-{uuid.uuid4()}"
        record = {
            "optimization_id": opt_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "budget": 10000.0,
            "allocated_budget": 5000.0,
            "remaining_budget": 5000.0,
            "total_expected_benefit": 45.0,
            "estimated_health_improvement": 10.0,
            "estimated_risk_reduction": 5.0,
            "selected_count": 1,
            "candidate_count": 2,
            "solver_status": "OPTIMAL",
            "selected_segments": [],
            "unselected_segments": []
        }
        save_optimization(record)
        
        response = client.get("/api/maintenance/optimization/latest")
        assert response.status_code == 200
        data = response.json()
        assert data["optimization_id"] == opt_id
        assert data["budget"] == 10000.0

    def test_invalid_budget_returns_422(self, client):
        """17. Validate /api/maintenance/optimize rejects negative budget with 422."""
        payload = {
            "budget": -500.0,
            "road_segments": []
        }
        response = client.post("/api/maintenance/optimize", json=payload)
        assert response.status_code == 422
