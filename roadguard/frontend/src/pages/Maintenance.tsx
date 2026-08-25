import { useEffect, useState } from 'react'
import apiService, { InspectionRecord } from '../services/api'

function priorityBadgeClass(p: string) {
  if (p === 'Immediate') return 'badge-immediate'
  if (p === 'High') return 'badge-high'
  if (p === 'Medium') return 'badge-medium'
  return 'badge-routine'
}

export default function MaintenancePage() {
  const [queue, setQueue] = useState<InspectionRecord[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiService.maintenanceQueue()
      .then(setQueue)
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="loading"><div className="spinner" /><span>Loading maintenance queue…</span></div>

  return (
    <div>
      <div className="page-header">
        <h2>Maintenance Priority Queue</h2>
        <p>Road segments ranked by urgency based on severity, health, and defect density.</p>
      </div>

      <div className="card" style={{ marginBottom: 20, padding: '16px 24px' }}>
        <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: 1.7 }}>
          <strong style={{ color: 'var(--text-secondary)' }}>Priority Formula:</strong>{' '}
          priority_score = (severity_score × 0.5) + ((100 − road_health) × 0.4) + min(20, detections × 5)
        </div>
      </div>

      {queue.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <h3>No inspections in queue.</h3>
            <p>Submit road images via the Detection page to populate the maintenance queue.</p>
          </div>
        </div>
      ) : (
        queue.map((r, i) => (
          <div key={r.inspection_id} className="queue-card">
            <div className="queue-rank">#{i + 1}</div>
            <div className="queue-info">
              <h4>{r.address || r.image_name}</h4>
              <p>
                {new Date(r.timestamp).toLocaleDateString()} &nbsp;·&nbsp;
                {r.detection_count} defect{r.detection_count !== 1 ? 's' : ''} &nbsp;·&nbsp;
                Road health: {r.road_health_score}/100
              </p>
              <div style={{ marginTop: 6, display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {r.damage_classes
                  ? (() => {
                      try { return (JSON.parse(r.damage_classes) as string[]).map(c => <span key={c} className="chip">{c}</span>) }
                      catch { return null }
                    })()
                  : null}
              </div>
            </div>
            <div className="queue-score">
              <div className="score-num">{r.priority_score}</div>
              <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: 4 }}>score</div>
              <span className={`badge ${priorityBadgeClass(r.priority)}`}>{r.priority}</span>
            </div>
          </div>
        ))
      )}
    </div>
  )
}
