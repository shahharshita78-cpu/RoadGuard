import { useRef, useState } from 'react'
import apiService, { AnalysisResult, Detection } from '../services/api'

function severityBadgeClass(s: string) {
  return s === 'High' ? 'badge-high' : s === 'Medium' ? 'badge-medium' : 'badge-low'
}
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

const CLASS_COLORS: Record<string, string> = {
  D00: '#22d3ee', D10: '#fbbf24', D20: '#fb923c', D40: '#f87171',
}

function DetectionCanvas({ src, detections, imgW, imgH }: {
  src: string; detections: Detection[]; imgW: number; imgH: number
}) {
  const imgRef = useRef<HTMLImageElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)

  const drawBoxes = () => {
    const img = imgRef.current; const canvas = canvasRef.current
    if (!img || !canvas) return
    const scaleX = img.clientWidth / imgW
    const scaleY = img.clientHeight / imgH
    canvas.width = img.clientWidth
    canvas.height = img.clientHeight
    const ctx = canvas.getContext('2d')!
    ctx.clearRect(0, 0, canvas.width, canvas.height)
    detections.forEach(d => {
      const { x1, y1, x2, y2 } = d.bbox
      const color = CLASS_COLORS[d.damage_class] || '#fbbf24'
      const sx = x1 * scaleX, sy = y1 * scaleY
      const sw = (x2 - x1) * scaleX, sh = (y2 - y1) * scaleY
      ctx.strokeStyle = color; ctx.lineWidth = 2
      ctx.strokeRect(sx, sy, sw, sh)
      ctx.fillStyle = color
      ctx.font = 'bold 11px Inter, sans-serif'
      const label = `${d.damage_class} ${(d.confidence * 100).toFixed(0)}%`
      const tw = ctx.measureText(label).width + 8
      ctx.fillRect(sx, sy - 18, tw, 18)
      ctx.fillStyle = '#0a0e1a'
      ctx.fillText(label, sx + 4, sy - 4)
    })
  }

  return (
    <div style={{ position: 'relative', display: 'inline-block', maxWidth: '100%', width: '100%' }}>
      <img ref={imgRef} src={src} alt="Detection result" onLoad={drawBoxes}
        style={{ display: 'block', width: '100%', borderRadius: 12 }} />
      <canvas ref={canvasRef} onLoad={drawBoxes}
        style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', pointerEvents: 'none' }} />
    </div>
  )
}

export default function DetectionPage() {
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [confidence, setConfidence] = useState(0.25)
  const [useManual, setUseManual] = useState(false)
  const [manualLat, setManualLat] = useState('')
  const [manualLon, setManualLon] = useState('')
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [drag, setDrag] = useState(false)

  const handleFile = (f: File) => {
    setFile(f); setResult(null); setError(null)
    setPreview(URL.createObjectURL(f))
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault(); setDrag(false)
    const f = e.dataTransfer.files[0]
    if (f) handleFile(f)
  }

  const handleSubmit = async () => {
    if (!file) return
    setLoading(true); setError(null)
    try {
      const res = await apiService.detect(
        file, confidence,
        useManual && manualLat ? parseFloat(manualLat) : undefined,
        useManual && manualLon ? parseFloat(manualLon) : undefined,
      )
      setResult(res)
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Detection failed. Is the backend running?')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <div className="page-header">
        <h2>Road Damage Detection</h2>
        <p>Upload a road image to detect and analyse surface damage in real time.</p>
      </div>

      <div className="grid-2" style={{ alignItems: 'start' }}>
        {/* Upload panel */}
        <div>
          <div
            className={`upload-zone ${drag ? 'drag-active' : ''}`}
            onDragOver={e => { e.preventDefault(); setDrag(true) }}
            onDragLeave={() => setDrag(false)}
            onDrop={handleDrop}
            onClick={() => document.getElementById('file-input')!.click()}
          >
            <div className="upload-icon">🛣️</div>
            <h3>{file ? file.name : 'Drop an image here'}</h3>
            <p>JPEG, PNG, or HEIC — click or drag to upload</p>
            <input id="file-input" type="file" accept=".jpg,.jpeg,.png,.heic,.heif"
              style={{ display: 'none' }} onChange={e => e.target.files?.[0] && handleFile(e.target.files[0])} />
          </div>

          <div className="card" style={{ marginTop: 16 }}>
            <div className="slider-wrap" style={{ marginBottom: 16 }}>
              <label>Confidence Threshold</label>
              <input type="range" min={0.05} max={0.95} step={0.05}
                value={confidence} onChange={e => setConfidence(+e.target.value)} />
              <span className="slider-value">{(confidence * 100).toFixed(0)}%</span>
            </div>

            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.85rem', color: 'var(--text-secondary)', cursor: 'pointer', marginBottom: 12 }}>
              <input type="checkbox" checked={useManual} onChange={e => setUseManual(e.target.checked)} />
              Override GPS coordinates manually
            </label>
            {useManual && (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 12 }}>
                {[['Latitude', manualLat, setManualLat], ['Longitude', manualLon, setManualLon]].map(([label, val, set]) => (
                  <div key={label as string}>
                    <label style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block', marginBottom: 4 }}>{label as string}</label>
                    <input type="number" step="0.000001" value={val as string}
                      onChange={e => (set as any)(e.target.value)}
                      style={{ width: '100%', padding: '8px 10px', background: 'var(--bg-primary)', border: '1px solid var(--border)', borderRadius: 6, color: 'var(--text-primary)', fontSize: '0.85rem' }} />
                  </div>
                ))}
              </div>
            )}

            <button className="btn btn-primary" style={{ width: '100%', justifyContent: 'center' }}
              onClick={handleSubmit} disabled={!file || loading}>
              {loading ? <><div className="spinner" style={{ width: 16, height: 16, borderWidth: 2 }} />Analysing…</> : '🔍 Run Detection'}
            </button>
          </div>

          {error && <div style={{ marginTop: 12, padding: '12px 16px', background: 'rgba(248,113,113,0.1)', border: '1px solid rgba(248,113,113,0.2)', borderRadius: 8, color: 'var(--red)', fontSize: '0.85rem' }}>{error}</div>}
        </div>

        {/* Preview & results */}
        <div>
          {preview && (
            <div className="card" style={{ marginBottom: 16 }}>
              <div className="card-header"><span className="card-title">Image Preview</span></div>
              {result
                ? <DetectionCanvas src={preview} detections={result.detections} imgW={result.image_width} imgH={result.image_height} />
                : <img src={preview} alt="Preview" style={{ width: '100%', borderRadius: 8 }} />
              }
            </div>
          )}

          {result && (
            <div className="result-panel">
              {/* Score summary */}
              <div className="grid-3" style={{ marginBottom: 16 }}>
                <div className="card" style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 6 }}>Detections</div>
                  <div style={{ fontSize: '2rem', fontWeight: 800, color: 'var(--cyan)' }}>{result.detection_count}</div>
                </div>
                <div className="card" style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 6 }}>Severity</div>
                  <div style={{ fontSize: '2rem', fontWeight: 800, color: 'var(--amber)' }}>{result.severity.severity_score}</div>
                  <span className={`badge ${severityBadgeClass(result.severity.severity)}`}>{result.severity.severity}</span>
                </div>
                <div className="card" style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 6 }}>Road Health</div>
                  <div style={{ fontSize: '2rem', fontWeight: 800, color: 'var(--green)' }}>{result.road_health.road_health_score}</div>
                  <span className={`badge ${conditionBadgeClass(result.road_health.road_condition)}`}>{result.road_health.road_condition}</span>
                </div>
              </div>

              {/* Detections table */}
              {result.detections.length > 0 && (
                <div className="card" style={{ marginBottom: 16 }}>
                  <div className="card-header"><span className="card-title">Individual Detections</span></div>
                  <div className="table-wrap">
                    <table>
                      <thead><tr><th>Class</th><th>Confidence</th><th>Bounding Box</th></tr></thead>
                      <tbody>
                        {result.detections.map((d, i) => (
                          <tr key={i}>
                            <td><span className="chip">{d.damage_class}</span></td>
                            <td>{(d.confidence * 100).toFixed(1)}%</td>
                            <td style={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>[{d.bbox.x1}, {d.bbox.y1}, {d.bbox.x2}, {d.bbox.y2}]</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Maintenance priority */}
              <div className="card">
                <div className="card-header">
                  <span className="card-title">Maintenance Priority</span>
                  <span className={`badge ${priorityBadgeClass(result.maintenance_priority.priority)}`}>{result.maintenance_priority.priority}</span>
                </div>
                <div className="score-bar-wrap" style={{ marginBottom: 12 }}>
                  <div className="score-bar-label"><span>Priority Score</span><span>{result.maintenance_priority.priority_score} / 100</span></div>
                  <div className="score-bar-track">
                    <div className="score-bar-fill amber" style={{ width: `${result.maintenance_priority.priority_score}%` }} />
                  </div>
                </div>
                <ul className="reason-list">
                  {result.maintenance_priority.reasons.map((r, i) => <li key={i}>{r}</li>)}
                </ul>
                {result.address && <div style={{ marginTop: 12, padding: '8px 12px', background: 'rgba(34,211,238,0.05)', borderRadius: 6, fontSize: '0.82rem', color: 'var(--cyan)' }}>📍 {result.address}</div>}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
