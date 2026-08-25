import { useEffect, useState } from 'react'
import apiService, { AnalyticsSummary } from '../services/api'
import {
  RadarChart, PolarGrid, PolarAngleAxis, Radar, ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, Tooltip, Cell
} from 'recharts'

const COLORS = ['#fbbf24', '#22d3ee', '#34d399', '#f87171', '#fb923c']

export default function Dashboard() {
  const [data, setData] = useState<AnalyticsSummary | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiService.analyticsSummary()
      .then(setData)
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="loading"><div className="spinner" /><span>Loading dashboard…</span></div>
  if (!data) return <div className="empty-state"><h3>Could not load analytics.</h3></div>

  const classDist = Object.entries(data.class_distribution).map(([name, value]) => ({ name, value }))
  const prioData  = Object.entries(data.priority_distribution).map(([name, value]) => ({ name, value }))

  const healthPct = data.avg_road_health
  const conditionColor = healthPct >= 70 ? 'green' : healthPct >= 40 ? 'amber' : 'red'

  return (
    <div>
      <div className="page-header">
        <h2>Dashboard</h2>
        <p>Real-time overview of road infrastructure health across all inspections.</p>
      </div>

      <div className="kpi-grid">
        <div className="kpi-card amber">
          <div className="kpi-label">Total Inspections</div>
          <div className="kpi-value">{data.total_inspections}</div>
          <div className="kpi-sub">All time</div>
        </div>
        <div className="kpi-card cyan">
          <div className="kpi-label">Total Defects</div>
          <div className="kpi-value">{data.total_detections}</div>
          <div className="kpi-sub">Detected across all images</div>
        </div>
        <div className="kpi-card red">
          <div className="kpi-label">Critical Segments</div>
          <div className="kpi-value">{data.critical_inspections}</div>
          <div className="kpi-sub">Road health score &lt; 30</div>
        </div>
        <div className={`kpi-card ${conditionColor}`}>
          <div className="kpi-label">Avg Road Health</div>
          <div className="kpi-value">{data.avg_road_health.toFixed(0)}</div>
          <div className="kpi-sub">Out of 100</div>
        </div>
      </div>

      <div className="grid-2">
        <div className="card">
          <div className="card-header">
            <span className="card-title">Defect Class Distribution</span>
          </div>
          {classDist.length === 0
            ? <div className="empty-state"><p>No detections yet.</p></div>
            : <ResponsiveContainer width="100%" height={220}>
                <BarChart data={classDist} barCategoryGap="30%">
                  <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 12 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={{ background: '#0f1525', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 8, color: '#f1f5f9' }} />
                  <Bar dataKey="value" radius={[6,6,0,0]}>
                    {classDist.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
          }
        </div>

        <div className="card">
          <div className="card-header">
            <span className="card-title">Maintenance Priority Distribution</span>
          </div>
          {prioData.length === 0
            ? <div className="empty-state"><p>No inspections yet.</p></div>
            : <ResponsiveContainer width="100%" height={220}>
                <BarChart data={prioData} layout="vertical" barCategoryGap="30%">
                  <XAxis type="number" tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis dataKey="name" type="category" tick={{ fill: '#94a3b8', fontSize: 12 }} axisLine={false} tickLine={false} width={80} />
                  <Tooltip contentStyle={{ background: '#0f1525', border: '1px solid rgba(255,255,255,0.08)', borderRadius: 8, color: '#f1f5f9' }} />
                  <Bar dataKey="value" radius={[0,6,6,0]}>
                    {prioData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
          }
        </div>
      </div>

      <div className="divider" />

      <div className="card">
        <div className="card-header">
          <span className="card-title">Avg Severity Score</span>
        </div>
        <div className="score-bar-wrap">
          <div className="score-bar-label">
            <span>Severity</span>
            <span>{data.avg_severity_score.toFixed(0)} / 100</span>
          </div>
          <div className="score-bar-track">
            <div className="score-bar-fill amber" style={{ width: `${data.avg_severity_score}%` }} />
          </div>
        </div>
        <div className="score-bar-wrap" style={{ marginTop: 12 }}>
          <div className="score-bar-label">
            <span>Road Health</span>
            <span>{data.avg_road_health.toFixed(0)} / 100</span>
          </div>
          <div className="score-bar-track">
            <div className="score-bar-fill green" style={{ width: `${data.avg_road_health}%` }} />
          </div>
        </div>
      </div>
    </div>
  )
}
