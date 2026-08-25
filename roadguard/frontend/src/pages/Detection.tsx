import { useEffect, useRef, useState } from 'react'
import apiService, { AnalysisResult, Detection as APIDetection } from '../services/api'

const CLASS_COLORS: Record<string, string> = {
  D00: '#94a3b8', D10: '#3fa66b', D20: '#d98a3a', D40: '#d45b5b',
}

function DetectionCanvas({ src, detections, imgW, imgH }: {
  src: string
  detections: APIDetection[]
  imgW: number
  imgH: number
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const img = new Image()
    img.src = src
    img.onload = () => {
      canvas.width = img.width
      canvas.height = img.height
      ctx.drawImage(img, 0, 0)

      const scaleX = img.width / imgW
      const scaleY = img.height / imgH

      detections.forEach((d: APIDetection) => {
        const { x1, y1, x2, y2 } = d.bbox
        const color = CLASS_COLORS[d.damage_class] || '#94a3b8'
        const sx = x1 * scaleX, sy = y1 * scaleY
        const sw = (x2 - x1) * scaleX, sh = (y2 - y1) * scaleY
        ctx.strokeStyle = color; ctx.lineWidth = 3
        ctx.strokeRect(sx, sy, sw, sh)
        ctx.fillStyle = color
        ctx.font = 'bold 12px monospace'
        const label = `${d.damage_class} ${(d.confidence * 100).toFixed(0)}%`
        const tw = ctx.measureText(label).width + 8
        ctx.fillRect(sx, sy - 18, tw, 18)
        ctx.fillStyle = '#ffffff'
        ctx.fillText(label, sx + 4, sy - 4)
      })
    }
  }, [src, detections, imgW, imgH])

  return (
    <div className="detection-canvas-wrap">
      <canvas ref={canvasRef} style={{ maxWidth: '100%', display: 'block', borderRadius: 'var(--radius-sm)' }} />
    </div>
  )
}

function severityBadgeClass(s: string) {
  if (s === 'High') return 'badge-high'
  if (s === 'Medium') return 'badge-medium'
  return 'badge-low'
}
function priorityBadgeClass(p: string) {
  if (p === 'Immediate') return 'badge-immediate'
  if (p === 'Critical') return 'badge-critical'
  if (p === 'Routine') return 'badge-routine'
  return 'badge-medium'
}

export default function Detection() {
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<string | null>(null)
  const [confidence, setConfidence] = useState(0.4)
  const [useManual, setUseManual] = useState(false)
  const [manualLat, setManualLat] = useState('')
  const [manualLon, setManualLon] = useState('')
  const [result, setResult] = useState<AnalysisResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [drag, setDrag] = useState(false)

  // Progress loaders state
  const [progressVal, setProgressVal] = useState(0)
  const [analysing, setAnalysing] = useState(false)

  const handleFile = (f: File) => {
    setFile(f); setResult(null); setError(null)
    const reader = new FileReader()
    reader.onloadend = () => setPreview(reader.result as string)
    reader.readAsDataURL(f)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault(); setDrag(false)
    if (e.dataTransfer.files?.[0]) handleFile(e.dataTransfer.files[0])
  }

  const handleSubmit = async () => {
    if (!file) return
    setLoading(true); setError(null)
    setAnalysing(true); setProgressVal(0)

    let progress = 0
    const timer = setInterval(() => {
      progress += Math.floor(Math.random() * 8) + 2
      if (progress >= 95) {
        progress = 95
        clearInterval(timer)
      }
      setProgressVal(progress)
    }, 100)

    try {
      const res = await apiService.detect(
        file, confidence,
        useManual && manualLat ? parseFloat(manualLat) : undefined,
        useManual && manualLon ? parseFloat(manualLon) : undefined,
      )
      clearInterval(timer)
      setProgressVal(100)
      setTimeout(() => {
        setResult(res)
        setAnalysing(false)
      }, 150)
    } catch (e: any) {
      clearInterval(timer)
      setAnalysing(false)
      setError(e.response?.data?.detail || 'Detection failed. Is the backend running?')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="control-room-grid" style={{ minHeight: '100%' }}>
      <div className="page-header">
        <h2>Image Inspection Workstation</h2>
        <p>GIS-referenced road surface surveys and image anomaly analysis</p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: 20, alignItems: 'start' }}>
        {/* Left Column: Image viewer workspace */}
        <div className="card" style={{ minHeight: 400, display: 'flex', flexDirection: 'column', justifyContent: 'center', background: 'var(--bg-primary)', border: '1px solid var(--border)', padding: 12 }}>
          {analysing ? (
            <div style={{ width: '100%', padding: '40px 20px', textAlign: 'center' }}>
              <div style={{ fontSize: '0.75rem', fontWeight: 800, color: 'var(--border-accent)', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 8 }}>
                ANALYSING ROAD
              </div>
              <div className="analysis-progress-bar" style={{ width: '100%', marginBottom: 12 }}>
                <div className="analysis-progress-fill" style={{ width: `${progressVal}%` }} />
              </div>
              <div style={{ fontSize: '0.85rem', fontFamily: 'monospace', color: 'var(--text-primary)', fontWeight: 700, marginBottom: 4 }}>
                {progressVal}%
              </div>
              <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                Detecting surface defects...
              </div>
            </div>
          ) : preview ? (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10 }}>
              <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 700, letterSpacing: '0.05em' }}>
                SURVEY IMAGE VIEWPORT
              </div>
              {result ? (
                <DetectionCanvas src={preview} detections={result.detections} imgW={result.image_width} imgH={result.image_height} />
              ) : (
                <img src={preview} alt="Survey preview" style={{ maxWidth: '100%', borderRadius: 'var(--radius-sm)' }} />
              )}
            </div>
          ) : (
            <div
              className={`upload-zone ${drag ? 'drag-active' : ''}`}
              onDragOver={e => { e.preventDefault(); setDrag(true) }}
              onDragLeave={() => setDrag(false)}
              onDrop={handleDrop}
              onClick={() => document.getElementById('file-input')!.click()}
              style={{ border: '1px dashed var(--border)', background: 'var(--bg-card-hover)', padding: '60px 20px' }}
            >
              <div style={{ fontSize: '1.1rem', fontWeight: 800, color: 'var(--text-secondary)', letterSpacing: '0.05em', textTransform: 'uppercase', marginBottom: 6 }}>
                DROP ROAD IMAGE
              </div>
              <div style={{ fontSize: '1.75rem', fontWeight: 900, color: 'var(--border-accent)', margin: '4px 0' }}>+</div>
              <p style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.08em', marginBottom: 12 }}>JPEG / PNG / HEIC</p>
              <button className="btn btn-secondary" style={{ pointerEvents: 'none' }}>SELECT IMAGE</button>
              <input id="file-input" type="file" accept=".jpg,.jpeg,.png,.heic,.heif"
                style={{ display: 'none' }} onChange={e => e.target.files?.[0] && handleFile(e.target.files[0])} />
            </div>
          )}
        </div>

        {/* Right Column: Engineering Control & Results panels */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          {/* Engineering Controls panel */}
          <div className="card card-dark">
            <div className="card-header"><span className="card-title">Survey Parameters</span></div>
            
            {file && (
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--bg-primary)', padding: '8px 12px', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', marginBottom: 12 }}>
                <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 200 }}>
                  {file.name}
                </span>
                <button className="btn" style={{ padding: '4px 8px', fontSize: '0.7rem', background: 'var(--bg-card-hover)', color: 'var(--text-primary)', border: '1px solid var(--border)', cursor: 'pointer' }} onClick={() => { setFile(null); setPreview(null); setResult(null); }}>
                  Clear
                </button>
              </div>
            )}

            <div className="slider-wrap" style={{ marginBottom: 12 }}>
              <label>Detection Threshold</label>
              <input type="range" min={0.05} max={0.95} step={0.05}
                value={confidence} onChange={e => setConfidence(+e.target.value)} disabled={analysing} />
              <span className="slider-value">{(confidence * 100).toFixed(0)}%</span>
            </div>

            <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.8rem', color: 'var(--text-secondary)', cursor: 'pointer', marginBottom: 12, fontWeight: 600 }}>
              <input type="checkbox" checked={useManual} onChange={e => setUseManual(e.target.checked)} disabled={analysing} />
              MANUAL COORDINATE OVERRIDE
            </label>
            
            {useManual && (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 12 }}>
                {[['LATITUDE', manualLat, setManualLat], ['LONGITUDE', manualLon, setManualLon]].map(([label, val, set]) => (
                  <div key={label as string}>
                    <label style={{ fontSize: '0.65rem', color: 'var(--text-muted)', display: 'block', marginBottom: 4, fontWeight: 700 }}>{label as string}</label>
                    <input type="number" step="0.000001" value={val as string}
                      onChange={e => (set as any)(e.target.value)} disabled={analysing}
                      style={{ width: '100%' }} />
                  </div>
                ))}
              </div>
            )}

            <button className="btn btn-primary" style={{ width: '100%', justifyContent: 'center' }}
              onClick={handleSubmit} disabled={!file || loading || analysing}>
              {loading || analysing ? <><div className="spinner" style={{ width: 14, height: 14 }} />Analysing…</> : 'Execute Inspection'}
            </button>
          </div>

          {error && <div style={{ padding: '10px 14px', background: 'rgba(201,76,76,0.1)', border: '1px solid rgba(201,76,76,0.2)', borderRadius: 'var(--radius-sm)', color: 'var(--red)', fontSize: '0.78rem' }}>{error}</div>}

          {/* Results Analysis Console */}
          {result && !analysing && (
            <div className="result-panel" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
              <div className="card card-dark">
                <div className="card-header"><span className="card-title">Inspection Telemetry</span></div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                  <div style={{ background: 'var(--bg-dark-secondary)', padding: '10px 12px', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)' }}>
                    <div style={{ fontSize: '0.62rem', color: 'var(--text-muted)', fontWeight: 700 }}>DEFECT COUNT</div>
                    <div style={{ fontSize: '1.4rem', fontWeight: 800, color: 'var(--text-primary)', fontFamily: 'monospace', marginTop: 2 }}>{result.detection_count}</div>
                  </div>
                  <div style={{ background: 'var(--bg-dark-secondary)', padding: '10px 12px', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)' }}>
                    <div style={{ fontSize: '0.62rem', color: 'var(--text-muted)', fontWeight: 700 }}>DEFECT CLASSES</div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 2, marginTop: 4 }}>
                      {(Array.from(new Set(result.detections.map((d: APIDetection) => d.damage_class))) as string[]).map((cls: string) => (
                        <span key={cls} className="chip" style={{ margin: 0, padding: '1px 4px', fontSize: '0.6rem' }}>{cls}</span>
                      ))}
                      {result.detections.length === 0 && <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>None</span>}
                    </div>
                  </div>
                </div>

                <div className="divider" />

                <div className="score-bar-wrap">
                  <div className="score-bar-label"><span>Structural Severity</span><span>{result.severity.severity_score}/100</span></div>
                  <div className="score-bar-track">
                    <div className="score-bar-fill red" style={{ width: `${result.severity.severity_score}%` }} />
                  </div>
                </div>

                <div className="score-bar-wrap" style={{ marginTop: 10 }}>
                  <div className="score-bar-label"><span>Road Health Score</span><span>{result.road_health.road_health_score}/100</span></div>
                  <div className="score-bar-track">
                    <div className="score-bar-fill green" style={{ width: `${result.road_health.road_health_score}%` }} />
                  </div>
                </div>

                <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 12 }}>
                  <span style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>SEVERITY LEVEL</span>
                  <span className={`badge ${severityBadgeClass(result.severity.severity)}`}>{result.severity.severity}</span>
                </div>
              </div>

              {/* Maintenance priority block */}
              <div className="card card-dark">
                <div className="card-header">
                  <span className="card-title">Maintenance Dispatch Priority</span>
                  <span className={`badge ${priorityBadgeClass(result.maintenance_priority.priority)}`}>{result.maintenance_priority.priority}</span>
                </div>
                <div className="score-bar-wrap" style={{ marginBottom: 10 }}>
                  <div className="score-bar-label"><span>Priority Index</span><span>{result.maintenance_priority.priority_score} / 100</span></div>
                  <div className="score-bar-track">
                    <div className="score-bar-fill amber" style={{ width: `${result.maintenance_priority.priority_score}%` }} />
                  </div>
                </div>
                <ul className="reason-list">
                  {result.maintenance_priority.reasons.map((r: string, i: number) => <li key={i}>{r}</li>)}
                </ul>
                {(result.latitude || result.longitude) && (
                  <div style={{ marginTop: 12, padding: '10px 12px', background: 'var(--bg-dark-secondary)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                    <div style={{ fontWeight: 700, fontSize: '0.65rem', color: 'var(--text-muted)', marginBottom: 2 }}>GPS COORDINATES</div>
                    <div style={{ fontFamily: 'monospace' }}>LAT: {result.latitude ?? '–'}, LON: {result.longitude ?? '–'}</div>
                    {result.address && <div style={{ borderTop: '1px solid var(--border)', marginTop: 6, paddingTop: 4, color: 'var(--text-muted)' }}>Location: {result.address}</div>}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
