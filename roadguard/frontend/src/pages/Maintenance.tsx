import { useEffect, useState } from 'react'
import apiService, { InspectionRecord } from '../services/api'

function priorityBadgeClass(p: string) {
  if (p === 'Immediate') return 'badge-immediate'
  if (p === 'High') return 'badge-high'
  if (p === 'Medium') return 'badge-medium'
  return 'badge-routine'
}

function getRecommendedAction(priority: string, score: number) {
  if (priority === 'Immediate' || score >= 80) return 'DISPATCH IMMEDIATE REPAIR CREW'
  if (priority === 'High' || score >= 60) return 'SCHEDULE HOT-MIX PATCHING (7 DAYS)'
  if (priority === 'Medium' || score >= 40) return 'ROUTINE MONITORING & PREVENTATIVE FILL'
  return 'DEFER / SCHEDULED MAINTENANCE REVIEW'
}

export default function MaintenancePage() {
  const [queue, setQueue] = useState<InspectionRecord[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiService.maintenanceQueue()
      .then(setQueue)
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="loading"><div className="spinner" /><span>Computing prioritized dispatch queue…</span></div>

  return (
    <div>
      <div className="page-header">
        <h2>Engineering Work Queue</h2>
        <p>Prioritised road maintenance dispatches ranked by mathematical urgency score</p>
      </div>

      <div className="card" style={{ marginBottom: 20, padding: '14px 20px' }}>
        <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', lineHeight: 1.6, textTransform: 'uppercase', fontWeight: 600 }}>
          <span style={{ color: 'var(--border-accent)' }}>dispatch scoring algorithm:</span>{' '}
          priority = (severity × 0.5) + ((100 − health) × 0.4) + min(20, defects × 5)
        </div>
      </div>

      {queue.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <h3>Dispatch queue empty</h3>
            <p>Initiate image surveys or video inspections to populate the maintenance log.</p>
          </div>
        </div>
      ) : (
        <div className="card">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Rank</th>
                  <th>Road ID / Location</th>
                  <th>Health</th>
                  <th>Severity</th>
                  <th>Priority Score</th>
                  <th>Dispatch Level</th>
                  <th>Recommended Action</th>
                </tr>
              </thead>
              <tbody>
                {queue.map((r, i) => (
                  <tr key={r.inspection_id}>
                    <td style={{ fontFamily: 'monospace', fontWeight: 700, color: 'var(--border-accent)' }}>#{i + 1}</td>
                    <td style={{ fontWeight: 600 }}>
                      <div>{r.address || r.image_name}</div>
                      <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', marginTop: 2, fontFamily: 'monospace' }}>
                        ID: {r.inspection_id.toString().slice(0, 8)}
                      </div>
                    </td>
                    <td style={{ fontFamily: 'monospace' }}>{r.road_health_score}/100</td>
                    <td style={{ fontFamily: 'monospace' }}>{r.severity_score}/100</td>
                    <td style={{ fontFamily: 'monospace', fontWeight: 700 }}>{r.priority_score}</td>
                    <td>
                      <span className={`badge ${priorityBadgeClass(r.priority)}`}>{r.priority}</span>
                    </td>
                    <td style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-secondary)' }}>
                      {getRecommendedAction(r.priority, r.priority_score)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
