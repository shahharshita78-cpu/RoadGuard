import { useEffect, useState } from 'react'
import apiService, { AnalyticsSummary, InspectionRecord } from '../services/api'
import { MapContainer, TileLayer, CircleMarker, Popup, Polyline } from 'react-leaflet'

const SEVERITY_COLORS: Record<string, string> = {
  High: '#c94c4c', Medium: '#d97732', Low: '#4f8a5b',
}

const CLASS_LABELS: Record<string, string> = {
  D00: 'LONGITUDINAL CRACK',
  D10: 'TRANSVERSE CRACK',
  D20: 'ALLIGATOR CRACK',
  D40: 'POTHOLE',
}

const CLASS_SEVERITY_COLORS: Record<string, string> = {
  D00: 'var(--green)',
  D10: 'var(--green)',
  D20: 'var(--orange)',
  D40: 'var(--red)',
}

export default function Dashboard() {
  const [analytics, setAnalytics] = useState<AnalyticsSummary | null>(null)
  const [records, setRecords] = useState<InspectionRecord[]>([])
  const [queue, setQueue] = useState<InspectionRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedRecord, setSelectedRecord] = useState<InspectionRecord | null>(null)

  useEffect(() => {
    Promise.all([
      apiService.analyticsSummary(),
      apiService.listInspections(),
      apiService.maintenanceQueue()
    ]).then(([analyticsData, inspectionsData, queueData]) => {
      setAnalytics(analyticsData)
      setRecords(inspectionsData.filter(r => r.latitude && r.longitude))
      setQueue(queueData)
      if (inspectionsData.length > 0) {
        setSelectedRecord(inspectionsData[inspectionsData.length - 1])
      }
    }).finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="loading"><div className="spinner" /><span>Calibrating GIS Telemetry Console…</span></div>
  if (!analytics) return <div className="empty-state"><h3>Control system offline.</h3></div>

  const healthPct = analytics.avg_road_health
  const statusLabel = healthPct >= 70 ? 'STABLE' : healthPct >= 40 ? 'DETERIORATED' : 'CRITICAL'
  const statusColor = healthPct >= 70 ? 'var(--green)' : healthPct >= 40 ? 'var(--orange)' : 'var(--red)'

  // Circular gauge calculations
  const radius = 40
  const strokeWidth = 6
  const circumference = 2 * Math.PI * radius
  const strokeDashoffset = circumference - (healthPct / 100) * circumference

  const classDist = Object.entries(analytics.class_distribution).map(([code, value]) => ({
    code,
    name: CLASS_LABELS[code] || code,
    value
  }))
  const maxDefectVal = Math.max(...classDist.map(d => d.value), 1)

  const center: [number, number] = records.length > 0
    ? [records[records.length - 1].latitude!, records[records.length - 1].longitude!]
    : [20.5937, 78.9629]

  const polylineCoords = records
    .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
    .map(r => [r.latitude!, r.longitude!] as [number, number])

  return (
    <div className="control-room-grid" style={{ minHeight: '100%' }}>
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2>ROADGUARD</h2>
          <p style={{ color: 'var(--amber)', fontSize: '0.7rem', letterSpacing: '0.1em', fontWeight: 700 }}>
            ROAD CONDITION MONITORING & TELEMETRY
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.72rem', color: 'var(--text-secondary)', fontFamily: 'monospace' }}>
          <span className="pulse-dot" />
          <span>SYSTEM ONLINE</span>
        </div>
      </div>

      {/* Top Section: Dashboard Hero - Circular Gauge & Selected Segment Details */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 2fr', gap: 20, marginBottom: 20 }}>
        {/* SVG Circular health gauge */}
        <div className="card" style={{ display: 'flex', alignItems: 'center', gap: 24, padding: '24px 20px', background: 'var(--bg-secondary)' }}>
          <div style={{ position: 'relative', width: 110, height: 110, flexShrink: 0 }}>
            <svg viewBox="0 0 100 100" className="svg-gauge" style={{ width: '100%', height: '100%' }}>
              <circle cx="50" cy="50" r={radius} stroke="var(--border)" strokeWidth={strokeWidth} fill="transparent" />
              <circle cx="50" cy="50" r={radius} stroke={statusColor} strokeWidth={strokeWidth} fill="transparent"
                strokeDasharray={circumference}
                strokeDashoffset={strokeDashoffset}
                strokeLinecap="round"
                style={{
                  transition: 'stroke-dashoffset 0.8s ease-out',
                  transform: 'rotate(-90deg)',
                  transformOrigin: '50% 50%'
                }}
              />
              <text x="50" y="55" textAnchor="middle" fill="var(--text-primary)" fontSize="18" fontWeight="800" fontFamily="monospace">
                {healthPct.toFixed(0)}
              </text>
            </svg>
          </div>
          <div>
            <div style={{ fontSize: '0.62rem', color: 'var(--text-secondary)', fontWeight: 700, letterSpacing: '0.08em' }}>ROAD HEALTH</div>
            <div style={{ fontSize: '1.25rem', fontWeight: 800, margin: '2px 0 6px', color: 'var(--text-primary)', fontFamily: 'monospace' }}>
              {healthPct.toFixed(1)} / 100
            </div>
            <span className="badge" style={{ background: 'var(--bg-primary)', color: statusColor, borderColor: statusColor }}>
              {statusLabel}
            </span>
          </div>
        </div>

        {/* Selected Road Segment metadata details */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
          <div className="card-header" style={{ marginBottom: 10 }}>
            <span className="card-title">Active Segment Details</span>
            {selectedRecord && (
              <span style={{ fontSize: '0.72rem', color: 'var(--amber)', fontWeight: 700, fontFamily: 'monospace' }}>
                SEG-{selectedRecord.inspection_id.slice(0, 6).toUpperCase()}
              </span>
            )}
          </div>
          {selectedRecord ? (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 10 }}>
              {[
                ['Segment ID', `SEG-${selectedRecord.inspection_id.slice(0, 6).toUpperCase()}`],
                ['Date Evaluated', new Date(selectedRecord.timestamp).toLocaleDateString()],
                ['GIS Latitude', selectedRecord.latitude?.toFixed(5) ?? '–'],
                ['GIS Longitude', selectedRecord.longitude?.toFixed(5) ?? '–'],
                ['Last Inspection', new Date(selectedRecord.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })],
                ['Dispatch Priority', selectedRecord.priority]
              ].map(([lbl, val]) => (
                <div key={lbl} style={{ background: 'var(--bg-primary)', padding: '6px 10px', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)' }}>
                  <div style={{ fontSize: '0.58rem', color: 'var(--text-secondary)', fontWeight: 700 }}>{lbl}</div>
                  <div style={{ fontSize: '0.78rem', fontWeight: 700, color: 'var(--text-primary)', textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap', marginTop: 2, fontFamily: 'monospace' }}>{val}</div>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Select a marker on the map to review details.</div>
          )}
        </div>
      </div>

      {/* Large GIS Map (dominant element) */}
      <div className="card" style={{ marginBottom: 20, padding: 12 }}>
        <div className="card-header" style={{ borderBottom: 'none', marginBottom: 10 }}>
          <span className="card-title">GIS Geographic Visualization</span>
          <span style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', fontWeight: 600 }}>ROUTE SURVEY LINES PLOTTED</span>
        </div>
        <div className="map-container" style={{ height: 380 }}>
          <MapContainer center={center} zoom={records.length > 0 ? 12 : 5} style={{ height: '100%', width: '100%', background: 'var(--bg-dark)' }}>
            <TileLayer
              url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
              attribution='&copy; <a href="https://carto.com/">CARTO</a>'
            />
            {polylineCoords.length > 1 && (
              <Polyline positions={polylineCoords} color="var(--amber)" weight={2} dashArray="8, 6" />
            )}
            {records.map(r => {
              const isSelected = selectedRecord?.inspection_id === r.inspection_id
              return (
                <CircleMarker
                  key={r.inspection_id}
                  center={[r.latitude!, r.longitude!]}
                  radius={isSelected ? 10 : 7}
                  eventHandlers={{
                    click: () => setSelectedRecord(r)
                  }}
                  pathOptions={{
                    color: isSelected ? 'var(--amber)' : (SEVERITY_COLORS[r.severity] || '#d97732'),
                    fillColor: SEVERITY_COLORS[r.severity] || '#d97732',
                    fillOpacity: isSelected ? 0.95 : 0.7,
                    weight: isSelected ? 3 : 1.5,
                  }}
                >
                  <Popup>
                    <div style={{ fontFamily: 'monospace', fontSize: '0.75rem', lineHeight: 1.5 }}>
                      <div style={{ fontWeight: 700, color: 'var(--border-accent)', borderBottom: '1px solid var(--border)', paddingBottom: 2, marginBottom: 4 }}>
                        RG-{r.inspection_id.slice(0, 6).toUpperCase()}
                      </div>
                      <div>Health: {r.road_health_score}</div>
                      <div>Severity: {r.severity_score}</div>
                      <div>Priority: {r.priority}</div>
                      <div>Defects: {r.detection_count}</div>
                    </div>
                  </Popup>
                </CircleMarker>
              )
            })}
          </MapContainer>
        </div>
      </div>

      <div className="divider-yellow" />

      {/* Metric Visualizations & Live inspection Pulse */}
      <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1.1fr 0.9fr', gap: 20 }}>
        {/* Defect profile horizontal bars */}
        <div className="card">
          <div className="card-header"><span className="card-title">Defect Profile</span></div>
          {classDist.length === 0 ? (
            <div className="empty-state"><p>No defects logged.</p></div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {classDist.map(d => (
                <div key={d.code}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.72rem', color: 'var(--text-secondary)', fontWeight: 700, marginBottom: 4 }}>
                    <span style={{ display: 'flex', alignItems: 'center' }}>
                      <span style={{ display: 'inline-block', width: 6, height: 6, borderRadius: '50%', background: CLASS_SEVERITY_COLORS[d.code] || 'var(--amber)', marginRight: 6 }} />
                      {d.name}
                    </span>
                    <span style={{ fontFamily: 'monospace' }}>{d.value}</span>
                  </div>
                  <div className="horizontal-bar-track">
                    <div className="horizontal-bar-fill" style={{ width: `${(d.value / maxDefectVal) * 100}%`, background: 'var(--bg-dark)' }} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Live scan telemetry: Inspection Pulse */}
        <div className="card">
          <div className="card-header"><span className="card-title">Inspection Pulse</span></div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {[
              ['Inspections Logged Today', records.length],
              ['Immediate Actions Pending', queue.filter(q => q.priority === 'Immediate').length],
              ['Critical Incidents Scored', queue.filter(q => q.priority === 'Immediate' || q.priority === 'High').length],
              ['System Baseline Severity', `${analytics.avg_severity_score.toFixed(0)} / 100`]
            ].map(([lbl, val]) => (
              <div key={lbl.toString()} style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 8px', background: 'var(--bg-primary)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)' }}>
                <span style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', fontWeight: 600 }}>{lbl}</span>
                <span style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-primary)', fontFamily: 'monospace' }}>{val}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Queue Preview */}
        <div className="card">
          <div className="card-header"><span className="card-title">Maintenance Queue</span></div>
          {queue.length === 0 ? (
            <div className="empty-state"><p>Queue empty.</p></div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {queue.slice(0, 3).map(q => (
                <div key={q.inspection_id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--bg-primary)', padding: '8px 10px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)' }}>
                  <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 100 }}>
                    <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-primary)' }}>{q.image_name}</div>
                    <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>Score: {q.priority_score}</div>
                  </div>
                  <span className={`badge badge-${q.priority.toLowerCase()}`} style={{ fontSize: '0.6rem' }}>{q.priority}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
