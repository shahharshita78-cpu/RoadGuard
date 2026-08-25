import { useEffect, useState } from 'react'
import apiService, { PredictionResult, PredictiveModelMeta, PredictiveRiskSummary } from '../services/api'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  LineChart, Line, Legend
} from 'recharts'

function riskBadgeClass(cat: string) {
  if (cat === 'CRITICAL') return 'badge-critical'
  if (cat === 'HIGH') return 'badge-high'
  if (cat === 'MEDIUM') return 'badge-medium'
  return 'badge-low'
}

const RISK_COLORS = {
  LOW: '#4f8a5b',
  MEDIUM: '#ebd073',
  HIGH: '#d97732',
  CRITICAL: '#c94c4c'
}

const TOOLTIP_STYLE = {
  background: '#ffffff',
  border: '1px solid #dcdcd6',
  borderRadius: 4,
  color: '#161616',
  fontSize: 12,
}

export default function PredictiveAnalytics() {
  const [summary, setSummary] = useState<PredictiveRiskSummary | null>(null)
  const [modelMeta, setModelMeta] = useState<PredictiveModelMeta | null>(null)
  const [selectedRoad, setSelectedRoad] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [training, setTraining] = useState(false)
  const [trainStatus, setTrainStatus] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const fetchData = async () => {
    try {
      const sumData = await apiService.getPredictiveRiskSummary()
      const metaData = await apiService.getPredictiveModelMeta()
      setSummary(sumData)
      setModelMeta(metaData)
      if (sumData.latest_predictions.length > 0 && !selectedRoad) {
        setSelectedRoad(sumData.latest_predictions[0].road_segment_id)
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load predictive analytics data.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [])

  const handleRetrain = async () => {
    setTraining(true)
    setTrainStatus('Retraining XGBoost models chronologically...')
    try {
      const res = await apiService.retrainPredictiveModel(65)
      setTrainStatus('Model trained successfully.')
      setModelMeta(res.metadata)
      // Refresh summary
      const sumData = await apiService.getPredictiveRiskSummary()
      setSummary(sumData)
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Retraining failed.')
      setTrainStatus(null)
    } finally {
      setTraining(false)
    }
  }

  if (loading) {
    return (
      <div className="loading">
        <div className="spinner" />
        <span>Loading predictive model analytics...</span>
      </div>
    )
  }

  const selectedPrediction = summary?.latest_predictions.find(
    p => p.road_segment_id === selectedRoad
  )

  // Format historical trend data for the selected road
  // Filter all predictions for the selected road, sort chronologically
  const roadHistory = summary?.latest_predictions
    .filter(p => p.road_segment_id === selectedRoad)
    .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
    .map(p => ({
      date: new Date(p.timestamp).toLocaleDateString(),
      health: p.feature_snapshot?.road_health_score ?? 100.0,
      predicted_health: p.predicted_future_health,
      risk: p.risk_probability * 100.0
    })) || []

  // Risk counts distribution for chart
  const riskChartData = summary
    ? Object.entries(summary.risk_counts).map(([name, value]) => ({ name, value }))
    : []

  return (
    <div>
      <div className="page-header">
        <h2>Predictive Road Deterioration</h2>
        <p>Analyze deterioration risk using trained longitudinal XGBoost models to identify priority maintenance cases.</p>
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

      {/* Aggregate Overview Card Grid */}
      <div className="kpi-grid">
        <div className="kpi-card cyan">
          <div className="kpi-label">Roads Evaluated</div>
          <div className="kpi-value">{summary?.total_roads_evaluated ?? 0}</div>
          <div className="kpi-sub">Distinct segments analyzed</div>
        </div>
        <div className="kpi-card red">
          <div className="kpi-label">Critical Risk Segments</div>
          <div className="kpi-value">{summary?.risk_counts.CRITICAL ?? 0}</div>
          <div className="kpi-sub">Deterioration probability &gt;= 75%</div>
        </div>
        <div className="kpi-card amber">
          <div className="kpi-label">High Risk Segments</div>
          <div className="kpi-value">{summary?.risk_counts.HIGH ?? 0}</div>
          <div className="kpi-sub">Deterioration probability 50% - 75%</div>
        </div>
        <div className="kpi-card green">
          <div className="kpi-label">Average Deterioration Risk</div>
          <div className="kpi-value">
            {summary ? (summary.avg_risk_probability * 100).toFixed(1) : '0.0'}%
          </div>
          <div className="kpi-sub">Average probability across all segments</div>
        </div>
      </div>

      {/* Middle section: Risk distribution & Model details */}
      <div className="grid-2" style={{ marginBottom: 24 }}>
        {/* Risk Distribution Chart */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">Deterioration Risk Category Distribution</span>
          </div>
          {riskChartData.length === 0 ? (
            <div className="empty-state"><p>No prediction records available.</p></div>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={riskChartData} barCategoryGap="40%">
                <XAxis dataKey="name" tick={{ fill: '#4b5563', fontSize: 11 }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={TOOLTIP_STYLE} />
                <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                  {riskChartData.map((entry) => (
                    <Cell key={entry.name} fill={RISK_COLORS[entry.name as keyof typeof RISK_COLORS] || '#475569'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Model Meta Information */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">XGBoost Deterioration Model Info</span>
            <span className="badge badge-routine">Active</span>
          </div>
          {modelMeta && (
            <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 12 }}>
                <div>
                  <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>Model Version</div>
                  <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>v{modelMeta.version}</div>
                </div>
                <div>
                  <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>Training Date</div>
                  <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                    {new Date(modelMeta.training_date).toLocaleString()}
                  </div>
                </div>
                <div>
                  <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>Training Dataset</div>
                  <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                    {modelMeta.is_synthetic ? 'Synthetic (Prototype)' : 'Real Longitudinal'}
                  </div>
                </div>
                <div>
                  <div style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>Training Size</div>
                  <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                    {modelMeta.training_sample_count} samples ({modelMeta.validation_sample_count} validation)
                  </div>
                </div>
              </div>

              <div style={{ borderTop: '1px solid var(--border)', padding: '10px 0', marginTop: 10, paddingTop: 10 }}>
                <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: 6, fontSize: '0.78rem', textTransform: 'uppercase' }}>
                  Validation Performance Metrics
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
                  <div style={{ background: 'var(--bg-primary)', padding: '6px 10px', borderRadius: 6, textAlign: 'center' }}>
                    <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>ROC-AUC</div>
                    <div style={{ fontWeight: 700, color: 'var(--text-primary)', fontSize: '0.95rem' }}>
                      {modelMeta.validation_metrics.classifier.roc_auc.toFixed(2)}
                    </div>
                  </div>
                  <div style={{ background: 'var(--bg-primary)', padding: '6px 10px', borderRadius: 6, textAlign: 'center' }}>
                    <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>Precision</div>
                    <div style={{ fontWeight: 700, color: 'var(--text-primary)', fontSize: '0.95rem' }}>
                      {modelMeta.validation_metrics.classifier.precision.toFixed(2)}
                    </div>
                  </div>
                  <div style={{ background: 'var(--bg-primary)', padding: '6px 10px', borderRadius: 6, textAlign: 'center' }}>
                    <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>Recall (FNR)</div>
                    <div style={{ fontWeight: 700, color: 'var(--text-primary)', fontSize: '0.95rem' }}>
                      {modelMeta.validation_metrics.classifier.recall.toFixed(2)}
                    </div>
                  </div>
                </div>
                {modelMeta.is_synthetic && (
                  <div style={{ marginTop: 10, fontSize: '0.72rem', color: 'var(--text-muted)', fontStyle: 'italic', lineHeight: 1.4 }}>
                    Note: Metrics calculated on synthetic longitudinal dataset. Real-world accuracy requires historical segment inspections.
                  </div>
                )}
              </div>

              <div style={{ marginTop: 14 }}>
                <button
                  className="btn btn-secondary"
                  style={{ width: '100%', justifyContent: 'center' }}
                  onClick={handleRetrain}
                  disabled={training}
                >
                  {training ? 'Retraining model...' : 'Retrain Deterioration Model'}
                </button>
                {trainStatus && (
                  <div style={{ marginTop: 6, fontSize: '0.75rem', color: 'var(--text-secondary)', textAlign: 'center' }}>
                    {trainStatus}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Main content grid: Segment List (Left) and Segment Details (Right) */}
      <div className="grid-2" style={{ alignItems: 'start' }}>
        {/* Road segment evaluation table */}
        <div className="card">
          <div className="card-header">
            <span className="card-title">Evaluated Road Segments</span>
          </div>
          <div className="table-wrap" style={{ maxHeight: 500, overflowY: 'auto' }}>
            <table>
              <thead>
                <tr>
                  <th>Road ID</th>
                  <th>Current Health</th>
                  <th>Predicted Health</th>
                  <th>Deterioration Risk</th>
                  <th>Risk Level</th>
                </tr>
              </thead>
              <tbody>
                {summary?.latest_predictions.map(p => (
                  <tr
                    key={p.prediction_id}
                    onClick={() => setSelectedRoad(p.road_segment_id)}
                    style={{
                      cursor: 'pointer',
                      background: selectedRoad === p.road_segment_id ? 'var(--bg-card-hover)' : 'transparent',
                      borderLeft: selectedRoad === p.road_segment_id ? '4px solid var(--amber)' : 'none'
                    }}
                  >
                    <td style={{ fontWeight: 600 }}>{p.road_segment_id}</td>
                    <td>{p.feature_snapshot?.road_health_score ?? '–'}</td>
                    <td style={{ color: p.predicted_future_health < 50 ? 'var(--red)' : 'var(--text-primary)' }}>
                      {p.predicted_future_health}
                    </td>
                    <td>{(p.risk_probability * 100).toFixed(0)}%</td>
                    <td>
                      <span className={`badge ${riskBadgeClass(p.risk_category)}`}>
                        {p.risk_category}
                      </span>
                    </td>
                  </tr>
                ))}
                {(!summary || summary.latest_predictions.length === 0) && (
                  <tr>
                    <td colSpan={5} style={{ textAlign: 'center' }}>No segments evaluated yet.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Selected segment detailed prediction overview */}
        <div>
          {selectedPrediction ? (
            <div className="card">
              <div className="card-header">
                <span className="card-title">Segment Prediction Detail: {selectedRoad}</span>
                <span className={`badge ${riskBadgeClass(selectedPrediction.risk_category)}`}>
                  {selectedPrediction.risk_category} RISK
                </span>
              </div>

              {/* Urgency Recommendation Box */}
              <div style={{
                background: 'var(--bg-primary)',
                border: '1px solid var(--border)',
                borderRadius: 6,
                padding: '12px 16px',
                marginBottom: 16,
                color: 'var(--text-secondary)',
                fontSize: '0.85rem'
              }}>
                <div style={{ fontWeight: 600, textTransform: 'uppercase', fontSize: '0.75rem', letterSpacing: '0.05em', marginBottom: 4 }}>
                  Inspection Urgency Recommendation
                </div>
                {selectedPrediction.urgency_recommendation}
              </div>

              {/* Current vs Future Health Score comparison */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
                <div style={{ background: 'var(--bg-primary)', borderRadius: 6, padding: 12, textAlign: 'center' }}>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Current Health Index</div>
                  <div style={{ fontSize: '1.8rem', fontWeight: 800, color: 'var(--text-primary)' }}>
                    {selectedPrediction.feature_snapshot?.road_health_score ?? '–'}
                  </div>
                </div>
                <div style={{ background: 'var(--bg-primary)', borderRadius: 6, padding: 12, textAlign: 'center' }}>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>Predicted Future Health</div>
                  <div style={{ fontSize: '1.8rem', fontWeight: 800, color: 'var(--text-primary)' }}>
                    {selectedPrediction.predicted_future_health}
                  </div>
                </div>
              </div>

              {/* XGBoost Feature Importance / Contribution list */}
              <div style={{ marginBottom: 20 }}>
                <div style={{ fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8, fontSize: '0.8rem', textTransform: 'uppercase' }}>
                  Deterioration Factor Explanations
                </div>
                <ul className="reason-list">
                  {selectedPrediction.top_factors.slice(0, 4).map((f, i) => (
                    <li key={i} style={{ fontSize: '0.82rem', padding: '4px 0' }}>
                      <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{f.label}:</span>{' '}
                      {f.direction === 'increased' ? 'increased deterioration risk' : 'decreased risk'}{' '}
                      <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem' }}>
                        (relative impact: {f.importance.toFixed(2)})
                      </span>
                    </li>
                  ))}
                  {selectedPrediction.top_factors.length === 0 && (
                    <li style={{ color: 'var(--text-muted)', fontSize: '0.82rem' }}>
                      No major contributing factors identified. Baseline risk.
                    </li>
                  )}
                </ul>
              </div>

              {/* Historical Trend Chart */}
              {roadHistory.length > 1 && (
                <div style={{ borderTop: '1px solid var(--border)', paddingTop: 16 }}>
                  <div style={{ fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 8, fontSize: '0.8rem', textTransform: 'uppercase' }}>
                    Historical Condition Trend
                  </div>
                  <ResponsiveContainer width="100%" height={150}>
                    <LineChart data={roadHistory}>
                      <XAxis dataKey="date" tick={{ fill: '#70706b', fontSize: 9 }} axisLine={false} tickLine={false} />
                      <YAxis domain={[0, 100]} tick={{ fill: '#9b9b95', fontSize: 9 }} axisLine={false} tickLine={false} />
                      <Tooltip contentStyle={TOOLTIP_STYLE} />
                      <Legend verticalAlign="top" height={24} iconSize={10} wrapperStyle={{ fontSize: 10 }} />
                      <Line type="monotone" name="Observed Health" dataKey="health" stroke="#151515" strokeWidth={2} dot={{ r: 3 }} />
                      <Line type="monotone" name="Future Predicted" dataKey="predicted_health" stroke="#e5b52f" strokeWidth={1.5} strokeDasharray="3 3" dot={{ r: 2 }} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>
          ) : (
            <div className="card">
              <div className="empty-state">
                <h3>Select a Segment</h3>
                <p>Click on any road segment in the table to view the deterioration prediction explanation and historical trend.</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
