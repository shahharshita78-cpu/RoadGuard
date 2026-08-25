import { useEffect, useState } from 'react'
import apiService, {
  OptimizationResult,
  SelectedMaintenanceSegment,
  OptimizationCandidate
} from '../services/api'

function formatCurrency(val: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0
  }).format(val)
}

function riskBadgeClass(prob: number) {
  if (prob >= 0.75) return 'badge-critical'
  if (prob >= 0.50) return 'badge-high'
  if (prob >= 0.25) return 'badge-medium'
  return 'badge-low'
}

export default function MaintenanceOptimizer() {
  const [budget, setBudget] = useState<number>(250000)
  const [latestPlan, setLatestPlan] = useState<OptimizationResult | null>(null)
  const [candidates, setCandidates] = useState<OptimizationCandidate[]>([])
  const [loading, setLoading] = useState(true)
  const [optimizing, setOptimizing] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadData = async () => {
    try {
      // 1. Fetch latest predictions to list candidates in summary before run
      const summary = await apiService.getPredictiveRiskSummary()
      const list = summary.latest_predictions.map(p => ({
        road_segment_id: p.road_segment_id,
        road_health_score: p.feature_snapshot?.road_health_score ?? 100.0,
        severity_score: p.feature_snapshot?.severity_score ?? 0.0,
        priority_score: p.feature_snapshot?.priority_score ?? 0.0,
        detection_count: p.feature_snapshot?.detection_count ?? 0,
        deterioration_risk: p.risk_probability,
        predicted_future_health: p.predicted_future_health
      }))
      setCandidates(list)

      // 2. Fetch latest optimization run from DB
      const latest = await apiService.getLatestOptimizationPlan()
      setLatestPlan(latest)
    } catch (err: any) {
      // Don't error out hard on 404 for latest plan since it might be first run
      if (err.response?.status !== 404) {
        setError(err.response?.data?.detail || 'Failed to fetch candidate database.')
      }
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const handleOptimize = async () => {
    if (budget <= 0) {
      setError('Please enter a valid positive available budget.')
      return
    }
    setOptimizing(true)
    setError(null)
    try {
      const res = await apiService.optimizeMaintenancePlan({ budget })
      setLatestPlan(res)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Optimization solver failed.')
    } finally {
      setOptimizing(false)
    }
  }

  if (loading) {
    return (
      <div className="loading">
        <div className="spinner" />
        <span>Loading optimization candidate database...</span>
      </div>
    )
  }

  // Calculate pre-optimization candidate statistics
  // Let's compute estimated costs dynamically using the same formula
  const computedCandidates = candidates.map(c => {
    const base = 5000.0
    const defect = 1200.0 * c.detection_count
    const severity = 80.0 * c.severity_score
    const degradation = 60.0 * (100.0 - c.road_health_score)
    const surcharges = 0.0  // Simplified surcharges for pre-comp list
    const estCost = base + defect + severity + degradation + surcharges
    return { ...c, estCost }
  })

  const totalCandidateCost = computedCandidates.reduce((acc, curr) => acc + curr.estCost, 0)
  const avgCurrentHealth = candidates.length > 0
    ? candidates.reduce((acc, curr) => acc + curr.road_health_score, 0) / candidates.length
    : 100.0
  const avgDeteriorationRisk = candidates.length > 0
    ? candidates.reduce((acc, curr) => acc + (curr.deterioration_risk ?? 0.0), 0) / candidates.length
    : 0.0
  const highPriorityCandidateCount = candidates.filter(c => c.priority_score >= 65).length

  // Budget allocation percentages
  const allocatedPct = latestPlan && latestPlan.budget > 0
    ? (latestPlan.allocated_budget / latestPlan.budget) * 100
    : 0
  const remainingPct = 100 - allocatedPct

  return (
    <div>
      <div className="page-header">
        <h2>Budget-Constrained Maintenance Optimization</h2>
        <p>Optimize road segment repairs under fixed financial resources using Google OR-Tools knapsack constraints.</p>
      </div>

      {error && (
        <div style={{
          padding: '12px 16px',
          background: 'rgba(248,113,113,0.1)',
          border: '1px solid rgba(248,113,113,0.2)',
          borderRadius: 8,
          color: 'var(--red)',
          marginBottom: 16,
          fontSize: '0.85rem'
        }}>
          {error}
        </div>
      )}

      {/* Top Section: Budget Input & Pre-Optimization Candidate Summary */}
      <div className="grid-2" style={{ marginBottom: 24, alignItems: 'start' }}>
        {/* Budget Input & Controls */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">Available Budget Settings</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <label htmlFor="budget-input" style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                Set available repair budget (USD)
              </label>
              <input
                id="budget-input"
                type="number"
                value={budget}
                onChange={e => setBudget(Number(e.target.value))}
                style={{
                  background: 'var(--bg-primary)',
                  border: '1px solid var(--border)',
                  borderRadius: 6,
                  padding: '10px 14px',
                  color: 'var(--text-primary)',
                  fontSize: '1.2rem',
                  fontWeight: 600
                }}
              />
            </div>
            <button
              className="btn btn-primary"
              style={{ justifyContent: 'center', padding: '12px' }}
              onClick={handleOptimize}
              disabled={optimizing}
            >
              {optimizing ? 'Executing Solver...' : 'Optimize Maintenance Plan'}
            </button>
          </div>
        </div>

        {/* Candidate Summary Box */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">Candidate Segment database Summary</span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12 }}>
            {[
              ['Candidate Segments', candidates.length],
              ['Total Repair Backlog Cost', formatCurrency(totalCandidateCost)],
              ['Current Average Health', `${avgCurrentHealth.toFixed(1)}/100`],
              ['Average Degradation Risk', `${(avgDeteriorationRisk * 100).toFixed(0)}%`],
              ['High Priority Segments', highPriorityCandidateCount]
            ].map(([label, val]) => (
              <div key={label.toString()} style={{ background: 'var(--bg-primary)', borderRadius: 8, padding: '10px 14px' }}>
                <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 4 }}>{label}</div>
                <div style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-primary)' }}>{val}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Middle Section: Results Overview */}
      {latestPlan && (
        <div style={{ marginBottom: 24 }}>
          <div className="kpi-grid" style={{ marginBottom: 16 }}>
            <div className="kpi-card cyan">
              <div className="kpi-label">Allocated Budget</div>
              <div className="kpi-value">{formatCurrency(latestPlan.allocated_budget)}</div>
              <div className="kpi-sub">{latestPlan.selected_count} segments chosen</div>
            </div>
            <div className="kpi-card green">
              <div className="kpi-label">Remaining Budget</div>
              <div className="kpi-value">{formatCurrency(latestPlan.remaining_budget)}</div>
              <div className="kpi-sub">{(remainingPct).toFixed(0)}% unused</div>
            </div>
            <div className="kpi-card amber">
              <div className="kpi-label">Expected Net Benefit</div>
              <div className="kpi-value">{latestPlan.total_expected_benefit}</div>
              <div className="kpi-sub">Maximize target score sum</div>
            </div>
            <div className="kpi-card red">
              <div className="kpi-label">Avg Risk Reduction</div>
              <div className="kpi-value">{latestPlan.estimated_risk_reduction}%</div>
              <div className="kpi-sub">For chosen segments</div>
            </div>
          </div>

          {/* Allocation Progress Visualization */}
          <div className="card" style={{ padding: 16 }}>
            <div className="score-bar-label" style={{ marginBottom: 8 }}>
              <span>Budget Allocation status: {formatCurrency(latestPlan.allocated_budget)} / {formatCurrency(latestPlan.budget)}</span>
              <span>{allocatedPct.toFixed(1)}% allocated</span>
            </div>
            <div className="score-bar-track" style={{ height: 16, borderRadius: 8 }}>
              <div
                className="score-bar-fill cyan"
                style={{ width: `${allocatedPct}%`, borderRadius: 8, height: 16 }}
              />
            </div>
          </div>
        </div>
      )}

      {/* Bottom Sections: Selected repairs & Unselected list */}
      {latestPlan && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          {/* Selected maintenance list */}
          <div className="card">
            <div className="card-header">
              <span className="card-title">Optimal Selected Maintenance Plan</span>
              <span className="badge badge-high">OR-Tools Optimal</span>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Rank</th>
                    <th>Road ID</th>
                    <th>Current Health</th>
                    <th>Predicted Health</th>
                    <th>Risk</th>
                    <th>Priority</th>
                    <th>Repair Cost</th>
                    <th>Benefit Score</th>
                    <th>Selection Explanation Reasons</th>
                  </tr>
                </thead>
                <tbody>
                  {latestPlan.selected_segments.map((s, idx) => (
                    <tr key={s.segment_id}>
                      <td style={{ fontWeight: 600, color: 'var(--cyan)' }}>#{idx + 1}</td>
                      <td style={{ fontWeight: 600 }}>{s.segment_id}</td>
                      <td>{s.current_health}</td>
                      <td>{s.predicted_future_health}</td>
                      <td>
                        <span className={`badge ${riskBadgeClass(s.deterioration_risk)}`}>
                          {(s.deterioration_risk * 100).toFixed(0)}%
                        </span>
                      </td>
                      <td>{s.maintenance_priority}</td>
                      <td style={{ fontWeight: 600 }}>{formatCurrency(s.estimated_cost)}</td>
                      <td style={{ color: 'var(--amber)', fontWeight: 600 }}>{s.benefit_score}</td>
                      <td>
                        <ul className="reason-list" style={{ margin: 0, paddingLeft: 12 }}>
                          {s.reasons.map((r, i) => (
                            <li key={i} style={{ fontSize: '0.78rem' }}>{r}</li>
                          ))}
                        </ul>
                      </td>
                    </tr>
                  ))}
                  {latestPlan.selected_segments.length === 0 && (
                    <tr>
                      <td colSpan={9} style={{ textAlign: 'center' }}>No segments selected under current budget constraints.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Unselected candidates list */}
          <div className="card">
            <div className="card-header">
              <span className="card-title">Unselected Segment Candidates</span>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                {latestPlan.unselected_segments.length} segments not included
              </span>
            </div>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Road ID</th>
                    <th>Current Health</th>
                    <th>Future Health</th>
                    <th>Risk</th>
                    <th>Priority</th>
                    <th>Estimated Cost</th>
                    <th>Benefit Score</th>
                    <th>Unselected Explanation Reasons</th>
                  </tr>
                </thead>
                <tbody>
                  {latestPlan.unselected_segments.map(s => (
                    <tr key={s.segment_id}>
                      <td style={{ fontWeight: 600 }}>{s.segment_id}</td>
                      <td>{s.current_health}</td>
                      <td>{s.predicted_future_health}</td>
                      <td>{(s.deterioration_risk * 100).toFixed(0)}%</td>
                      <td>{s.maintenance_priority}</td>
                      <td>{formatCurrency(s.estimated_cost)}</td>
                      <td>{s.benefit_score}</td>
                      <td>
                        <ul className="reason-list" style={{ margin: 0, paddingLeft: 12, color: 'var(--text-muted)' }}>
                          {s.reasons.map((r, i) => (
                            <li key={i} style={{ fontSize: '0.78rem' }}>{r}</li>
                          ))}
                        </ul>
                      </td>
                    </tr>
                  ))}
                  {latestPlan.unselected_segments.length === 0 && (
                    <tr>
                      <td colSpan={8} style={{ textAlign: 'center' }}>No unselected segments. All candidates fit within budget.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
