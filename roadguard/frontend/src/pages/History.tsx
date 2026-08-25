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

  if (loading) return <div className="loading"><div className="spinner" /><span>Retrieving historical registry…</span></div>

  return (
    <div>
      <div className="page-header">
        <h2>Inspection Registry Log</h2>
        <p>GIS Log of all completed road condition assessments</p>
      </div>

      {records.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <h3>No records available</h3>
            <p>Initiate a new image inspection to populate the database log.</p>
          </div>
        </div>
      ) : (
        <div className="card">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Date</th>
                  <th>Location</th>
                  <th>Defects</th>
                  <th>Health</th>
                  <th>Severity</th>
                  <th>Priority</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {records.map(r => (
                  <tr key={r.inspection_id}>
                    <td style={{ fontFamily: 'monospace', fontWeight: 700 }}>#{r.inspection_id.toString().slice(0, 8)}</td>
                    <td style={{ whiteSpace: 'nowrap' }}>{formatDate(r.timestamp)}</td>
                    <td style={{ fontSize: '0.75rem', maxWidth: 180, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={r.address || ''}>
                      {r.latitude && r.longitude
                        ? `${r.latitude.toFixed(4)}, ${r.longitude.toFixed(4)}`
                        : '—'}
                    </td>
                    <td style={{ fontFamily: 'monospace', fontWeight: 600 }}>{r.detection_count}</td>
                    <td style={{ fontFamily: 'monospace', fontWeight: 600 }}>{r.road_health_score}/100</td>
                    <td style={{ fontFamily: 'monospace', fontWeight: 600 }}>{r.severity_score}/100</td>
                    <td>
                      <span className={`badge ${priorityBadgeClass(r.priority)}`}>{r.priority}</span>
                    </td>
                    <td>
                      <span className={`badge ${conditionBadgeClass(r.road_condition)}`}>{r.road_condition}</span>
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
