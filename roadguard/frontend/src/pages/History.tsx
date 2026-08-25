import { useEffect, useState } from 'react'
import apiService, { InspectionRecord } from '../services/api'

function priorityBadgeClass(p: string) {
  if (p === 'Immediate') return 'badge-immediate'
  if (p === 'High') return 'badge-high'
  if (p === 'Medium') return 'badge-medium'
  return 'badge-routine'
}
function conditionBadgeClass(c: string) {
  if (c === 'Critical') return 'badge-critical'
  if (c === 'Poor') return 'badge-high'
  if (c === 'Moderate') return 'badge-medium'
  return 'badge-low'
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' })
}

export default function History() {
  const [records, setRecords] = useState<InspectionRecord[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    apiService.listInspections()
      .then(setRecords)
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="loading"><div className="spinner" /><span>Loading inspections…</span></div>

  return (
    <div>
      <div className="page-header">
        <h2>Inspection History</h2>
        <p>Complete log of all road damage inspections.</p>
      </div>

      {records.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <h3>No inspections recorded yet.</h3>
            <p>Upload an image on the Detection page to create an inspection record.</p>
          </div>
        </div>
      ) : (
        <div className="card">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Image</th>
                  <th>Detections</th>
                  <th>Severity</th>
                  <th>Road Health</th>
                  <th>Priority</th>
                  <th>Location</th>
                </tr>
              </thead>
              <tbody>
                {records.map(r => (
                  <tr key={r.inspection_id}>
                    <td style={{ whiteSpace: 'nowrap' }}>{formatDate(r.timestamp)}</td>
                    <td style={{ maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={r.image_name}>{r.image_name}</td>
                    <td>{r.detection_count}</td>
                    <td>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                        <span style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--amber)' }}>{r.severity_score}</span>
                        <span className={`badge badge-${r.severity.toLowerCase()}`}>{r.severity}</span>
                      </div>
                    </td>
                    <td>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                        <span style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--green)' }}>{r.road_health_score}</span>
                        <span className={`badge ${conditionBadgeClass(r.road_condition)}`}>{r.road_condition}</span>
                      </div>
                    </td>
                    <td>
                      <span className={`badge ${priorityBadgeClass(r.priority)}`}>{r.priority}</span>
                    </td>
                    <td style={{ fontSize: '0.78rem', maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                      title={r.address || ''}>
                      {r.latitude && r.longitude
                        ? r.address || `${r.latitude.toFixed(4)}, ${r.longitude.toFixed(4)}`
                        : '—'}
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
