import { useEffect, useRef, useState } from 'react'
import apiService, { VideoInspectionRecord, FrameSummary } from '../services/api'
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
  BarChart, Bar, Cell
} from 'recharts'

// ── Helpers ──────────────────────────────────────────────────────────────────

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
function fmtSec(sec: number): string {
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return m > 0 ? `${m}m ${s}s` : `${s}s`
}

const CHART_COLORS = ['#fbbf24', '#22d3ee', '#34d399', '#f87171', '#fb923c']
const TOOLTIP_STYLE = {
  background: '#0f1525',
  border: '1px solid rgba(255,255,255,0.08)',
  borderRadius: 8,
  color: '#f1f5f9',
  fontSize: 12,
}

// ── History tab ───────────────────────────────────────────────────────────────

function HistoryRow({ r }: { r: VideoInspectionRecord }) {
  const [open, setOpen] = useState(false)
  return (
    <div style={{
      background: 'var(--bg-card)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius-md)',
      marginBottom: 10,
      transition: 'border-color var(--transition)',
      ...(open ? { borderColor: 'var(--border-accent)' } : {}),
    }}>
      <button
        style={{
          width: '100%', background: 'none', border: 'none', cursor: 'pointer',
          display: 'flex', alignItems: 'center', gap: 16,
          padding: '14px 20px', textAlign: 'left',
        }}
        onClick={() => setOpen(o => !o)}
        id={`video-history-row-${r.inspection_id}`}
      >
        <span style={{ fontSize: '1.4rem' }}>🎬</span>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 600, fontSize: '0.9rem', color: 'var(--text-primary)', marginBottom: 2 }}>
            {r.video_name}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            {new Date(r.timestamp).toLocaleString()} · {fmtSec(r.duration_seconds)} · {r.sampled_frames} frames sampled
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <span className={`badge ${severityBadgeClass(r.overall_severity)}`}>{r.overall_severity}</span>
          <span className={`badge ${conditionBadgeClass(r.road_condition)}`}>{r.road_condition}</span>
          <span style={{ color: 'var(--text-muted)', fontSize: '1rem' }}>{open ? '▲' : '▼'}</span>
        </div>
      </button>

      {open && (
        <div style={{ padding: '0 20px 20px', borderTop: '1px solid var(--border)' }}>
          <div className="grid-3" style={{ marginTop: 16, marginBottom: 16 }}>
            {[
              { label: 'Total Defects', val: r.total_detections, sub: `${r.unique_detections} unique`, color: 'var(--cyan)' },
              { label: 'Road Health', val: r.road_health_score, sub: r.road_condition, color: 'var(--green)' },
              { label: 'Priority Score', val: r.priority_score, sub: r.priority, color: 'var(--amber)' },
            ].map(({ label, val, sub, color }) => (
              <div key={label} className="card" style={{ textAlign: 'center', padding: 16 }}>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 4 }}>{label}</div>
                <div style={{ fontSize: '1.8rem', fontWeight: 800, color }}>{val}</div>
                <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: 2 }}>{sub}</div>
              </div>
            ))}
          </div>

          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginBottom: 4 }}>Damage classes detected:</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {Object.entries(r.class_distribution).map(([cls, cnt]) => (
              <span key={cls} className="chip">{cls} ×{cnt}</span>
            ))}
            {Object.keys(r.class_distribution).length === 0 && (
              <span style={{ color: 'var(--text-muted)', fontSize: '0.82rem' }}>None detected</span>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Results panel ─────────────────────────────────────────────────────────────

function ResultPanel({ result }: { result: VideoInspectionRecord }) {
  // Prepare frame-level chart data (downsample if > 60 frames for legibility)
  const frames: FrameSummary[] = result.frame_summaries
  const step = Math.max(1, Math.floor(frames.length / 60))
  const chartData = frames
    .filter((_, i) => i % step === 0)
    .map(f => ({
      t: fmtSec(f.timestamp_sec),
      health: f.road_health_score,
      severity: f.severity_score,
      detections: f.detection_count,
    }))

  const classDist = Object.entries(result.class_distribution).map(([name, value]) => ({ name, value }))

  return (
    <div className="result-panel" style={{ marginTop: 24 }}>
      {/* Top KPIs */}
      <div className="kpi-grid" style={{ marginBottom: 20 }}>
        <div className="kpi-card cyan">
          <div className="kpi-label">Unique Defects</div>
          <div className="kpi-value">{result.unique_detections}</div>
          <div className="kpi-sub">{result.total_detections} total detections (deduplicated)</div>
        </div>
        <div className="kpi-card amber">
          <div className="kpi-label">Frames w/ Damage</div>
          <div className="kpi-value">{result.damage_frame_pct}%</div>
          <div className="kpi-sub">{result.frames_with_damage} of {result.sampled_frames} sampled frames</div>
        </div>
        <div className="kpi-card green">
          <div className="kpi-label">Road Health</div>
          <div className="kpi-value">{result.road_health_score}</div>
          <div className="kpi-sub">{result.road_condition}</div>
        </div>
        <div className="kpi-card red">
          <div className="kpi-label">Priority</div>
          <div className="kpi-value">{result.priority_score}</div>
          <div className="kpi-sub">{result.priority}</div>
        </div>
      </div>

      {/* Video metadata */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-header">
          <span className="card-title">Video Details</span>
          <span className={`badge ${severityBadgeClass(result.overall_severity)}`}>
            {result.overall_severity} Severity
          </span>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: 12 }}>
          {[
            ['File', result.video_name],
            ['Duration', fmtSec(result.duration_seconds)],
            ['Total Frames', String(result.total_frames)],
            ['FPS', result.fps.toFixed(1)],
            ['Sampled Every', `${result.frame_interval} frames`],
            ['Avg Confidence', `${(result.avg_confidence * 100).toFixed(0)}%`],
          ].map(([label, val]) => (
            <div key={label} style={{ background: 'var(--bg-primary)', borderRadius: 8, padding: '10px 14px' }}>
              <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: 4 }}>{label}</div>
              <div style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-primary)', wordBreak: 'break-all' }}>{val}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Frame-level charts */}
      {chartData.length > 0 && (
        <div className="grid-2" style={{ marginBottom: 16 }}>
          <div className="card">
            <div className="card-header"><span className="card-title">Road Health over Time</span></div>
            <ResponsiveContainer width="100%" height={180}>
              <AreaChart data={chartData}>
                <defs>
                  <linearGradient id="healthGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#34d399" stopOpacity={0.25} />
                    <stop offset="95%" stopColor="#34d399" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="t" tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
                <YAxis domain={[0, 100]} tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={TOOLTIP_STYLE} />
                <Area type="monotone" dataKey="health" stroke="#34d399" fill="url(#healthGrad)" strokeWidth={2} dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>

          <div className="card">
            <div className="card-header"><span className="card-title">Severity Score over Time</span></div>
            <ResponsiveContainer width="100%" height={180}>
              <AreaChart data={chartData}>
                <defs>
                  <linearGradient id="sevGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#fbbf24" stopOpacity={0.25} />
                    <stop offset="95%" stopColor="#fbbf24" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="t" tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} interval="preserveStartEnd" />
                <YAxis domain={[0, 100]} tick={{ fill: '#64748b', fontSize: 10 }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={TOOLTIP_STYLE} />
                <Area type="monotone" dataKey="severity" stroke="#fbbf24" fill="url(#sevGrad)" strokeWidth={2} dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Class distribution + priority */}
      <div className="grid-2" style={{ marginBottom: 16 }}>
        <div className="card">
          <div className="card-header"><span className="card-title">Defect Class Distribution</span></div>
          {classDist.length === 0
            ? <div className="empty-state"><p>No damage detected in video.</p></div>
            : <ResponsiveContainer width="100%" height={180}>
                <BarChart data={classDist} barCategoryGap="35%">
                  <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 12 }} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fill: '#64748b', fontSize: 11 }} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={TOOLTIP_STYLE} />
                  <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                    {classDist.map((_, i) => <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
          }
        </div>

        <div className="card">
          <div className="card-header">
            <span className="card-title">Maintenance Priority</span>
            <span className={`badge ${priorityBadgeClass(result.priority)}`}>{result.priority}</span>
          </div>
          <div className="score-bar-wrap" style={{ marginBottom: 12 }}>
            <div className="score-bar-label"><span>Priority Score</span><span>{result.priority_score} / 100</span></div>
            <div className="score-bar-track">
              <div className="score-bar-fill amber" style={{ width: `${result.priority_score}%` }} />
            </div>
          </div>
          <div className="score-bar-wrap" style={{ marginBottom: 12 }}>
            <div className="score-bar-label"><span>Road Health</span><span>{result.road_health_score} / 100</span></div>
            <div className="score-bar-track">
              <div className="score-bar-fill green" style={{ width: `${result.road_health_score}%` }} />
            </div>
          </div>
          <div className="score-bar-wrap">
            <div className="score-bar-label"><span>Max Severity (single frame)</span><span>{result.max_severity_score} / 100</span></div>
            <div className="score-bar-track">
              <div className="score-bar-fill red" style={{ width: `${result.max_severity_score}%` }} />
            </div>
          </div>
          <ul className="reason-list" style={{ marginTop: 16 }}>
            {result.priority_reasons.map((r, i) => <li key={i}>{r}</li>)}
          </ul>
        </div>
      </div>

      {/* Frame-level table (collapsed — show worst 10) */}
      {frames.length > 0 && (
        <div className="card">
          <div className="card-header">
            <span className="card-title">Worst Frames (by severity)</span>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Top 10 of {frames.length} sampled</span>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Frame #</th>
                  <th>Detections</th>
                  <th>Severity</th>
                  <th>Road Health</th>
                  <th>Classes</th>
                </tr>
              </thead>
              <tbody>
                {[...frames]
                  .sort((a, b) => b.severity_score - a.severity_score)
                  .slice(0, 10)
                  .map(f => (
                    <tr key={f.frame_number}>
                      <td style={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>{fmtSec(f.timestamp_sec)}</td>
                      <td style={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>{f.frame_number}</td>
                      <td>{f.detection_count}</td>
                      <td>{f.severity_score}</td>
                      <td>{f.road_health_score}</td>
                      <td>{f.damage_classes.map(c => <span key={c} className="chip" style={{ marginRight: 4 }}>{c}</span>)}</td>
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

// ── Main page ─────────────────────────────────────────────────────────────────

type Tab = 'upload' | 'history'

export default function VideoInspectionPage() {
  const [tab, setTab] = useState<Tab>('upload')
  const [file, setFile] = useState<File | null>(null)
  const [drag, setDrag] = useState(false)
  const [frameInterval, setFrameInterval] = useState(30)
  const [confidence, setConfidence] = useState(0.25)
  const [uploadPct, setUploadPct] = useState<number | null>(null)
  const [processing, setProcessing] = useState(false)
  const [result, setResult] = useState<VideoInspectionRecord | null>(null)
  const [error, setError] = useState<string | null>(null)

  // History tab state
  const [history, setHistory] = useState<VideoInspectionRecord[]>([])
  const [histLoading, setHistLoading] = useState(false)

  const fileInputRef = useRef<HTMLInputElement>(null)

  const loadHistory = () => {
    setHistLoading(true)
    apiService.listVideoInspections()
      .then(setHistory)
      .catch(() => setHistory([]))
      .finally(() => setHistLoading(false))
  }

  useEffect(() => {
    if (tab === 'history') loadHistory()
  }, [tab])

  const handleFile = (f: File) => {
    setFile(f); setResult(null); setError(null); setUploadPct(null)
  }
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault(); setDrag(false)
    const f = e.dataTransfer.files[0]
    if (f) handleFile(f)
  }

  const handleSubmit = async () => {
    if (!file) return
    setProcessing(true); setError(null); setResult(null); setUploadPct(0)
    try {
      const res = await apiService.videoDetect(file, frameInterval, confidence, pct => setUploadPct(pct))
      setResult(res)
      setUploadPct(null)
    } catch (e: any) {
      const msg = e.response?.data?.detail || 'Processing failed. Is the backend running?'
      setError(typeof msg === 'string' ? msg : JSON.stringify(msg))
      setUploadPct(null)
    } finally {
      setProcessing(false)
    }
  }

  const estimatedFrames = file ? '–' : '–'  // server-side calculation

  return (
    <div>
      <div className="page-header">
        <h2>Video Road Inspection</h2>
        <p>Upload a road video to detect and aggregate surface damage across all sampled frames.</p>
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
        {(['upload', 'history'] as Tab[]).map(t => (
          <button
            key={t}
            id={`video-tab-${t}`}
            onClick={() => setTab(t)}
            className={`btn ${tab === t ? 'btn-primary' : 'btn-secondary'}`}
            style={{ minWidth: 120 }}
          >
            {t === 'upload' ? '📤 Analyse Video' : '📋 Past Inspections'}
          </button>
        ))}
      </div>

      {/* ── Upload tab ─────────────────────────────────────────────────────── */}
      {tab === 'upload' && (
        <div>
          <div className="grid-2" style={{ alignItems: 'start' }}>
            {/* Left: upload + controls */}
            <div>
              <div
                id="video-upload-zone"
                className={`upload-zone ${drag ? 'drag-active' : ''}`}
                onDragOver={e => { e.preventDefault(); setDrag(true) }}
                onDragLeave={() => setDrag(false)}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
              >
                <div className="upload-icon">🎬</div>
                <h3>{file ? file.name : 'Drop a road video here'}</h3>
                <p>MP4, AVI, MOV, MKV, WEBM, M4V — click or drag to upload</p>
                {file && (
                  <p style={{ marginTop: 6, color: 'var(--cyan)', fontSize: '0.78rem' }}>
                    {(file.size / 1024 / 1024).toFixed(1)} MB
                  </p>
                )}
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".mp4,.avi,.mov,.mkv,.webm,.m4v,.mpeg,.mpg"
                  style={{ display: 'none' }}
                  onChange={e => e.target.files?.[0] && handleFile(e.target.files[0])}
                  id="video-file-input"
                />
              </div>

              <div className="card" style={{ marginTop: 16 }}>
                <div style={{ marginBottom: 20 }}>
                  <div className="slider-wrap" style={{ marginBottom: 10 }}>
                    <label>Frame Interval</label>
                    <input type="range" min={5} max={120} step={5}
                      value={frameInterval} onChange={e => setFrameInterval(+e.target.value)} />
                    <span className="slider-value">every {frameInterval}</span>
                  </div>
                  <div style={{ fontSize: '0.73rem', color: 'var(--text-muted)', marginTop: 4, paddingLeft: 2 }}>
                    Lower = more frames analysed (slower); Higher = faster but may miss short damage events.
                    At 30 fps → sampling ~{(30 / frameInterval).toFixed(1)} fps.
                  </div>
                </div>

                <div className="slider-wrap" style={{ marginBottom: 20 }}>
                  <label>Confidence Threshold</label>
                  <input type="range" min={0.05} max={0.95} step={0.05}
                    value={confidence} onChange={e => setConfidence(+e.target.value)} />
                  <span className="slider-value">{(confidence * 100).toFixed(0)}%</span>
                </div>

                <button
                  id="video-detect-btn"
                  className="btn btn-primary"
                  style={{ width: '100%', justifyContent: 'center' }}
                  onClick={handleSubmit}
                  disabled={!file || processing}
                >
                  {processing
                    ? <><div className="spinner" style={{ width: 16, height: 16, borderWidth: 2 }} />
                        {uploadPct !== null && uploadPct < 100
                          ? `Uploading… ${uploadPct}%`
                          : 'Analysing frames…'}
                      </>
                    : '🎬 Run Video Inspection'}
                </button>

                {/* Upload progress bar */}
                {uploadPct !== null && (
                  <div style={{ marginTop: 12 }}>
                    <div className="score-bar-label">
                      <span>{uploadPct < 100 ? 'Uploading' : 'Processing'}</span>
                      <span>{uploadPct}%</span>
                    </div>
                    <div className="score-bar-track">
                      <div
                        className="score-bar-fill cyan"
                        style={{ width: `${uploadPct}%`, transition: 'width 0.3s ease' }}
                      />
                    </div>
                  </div>
                )}
              </div>

              {error && (
                <div style={{
                  marginTop: 12, padding: '12px 16px',
                  background: 'rgba(248,113,113,0.1)',
                  border: '1px solid rgba(248,113,113,0.2)',
                  borderRadius: 8, color: 'var(--red)', fontSize: '0.85rem',
                }}>
                  {error}
                </div>
              )}

              {/* How it works */}
              {!result && !processing && (
                <div className="card" style={{ marginTop: 16, padding: 20 }}>
                  <div className="card-header" style={{ marginBottom: 12 }}>
                    <span className="card-title">How it works</span>
                  </div>
                  <ol style={{ paddingLeft: 20, fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: 2 }}>
                    <li>Video is streamed to the server without loading it fully into memory.</li>
                    <li>One frame is sampled every <strong style={{ color: 'var(--amber)' }}>{frameInterval}</strong> frames (configurable).</li>
                    <li>YOLOv8 runs on each sampled frame to detect road damage.</li>
                    <li>Consecutive identical detections are deduplicated by IoU overlap to avoid double-counting.</li>
                    <li>Severity, Road Health, and Maintenance Priority are aggregated across all unique defects.</li>
                    <li>Results are persisted in SQLite and available in Past Inspections.</li>
                  </ol>
                </div>
              )}
            </div>

            {/* Right: results */}
            <div>
              {processing && !result && (
                <div className="card" style={{ textAlign: 'center', padding: '48px 24px' }}>
                  <div className="spinner" style={{ margin: '0 auto 16px', width: 36, height: 36, borderWidth: 3 }} />
                  <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
                    {uploadPct !== null && uploadPct < 100
                      ? `Uploading video (${uploadPct}%)…`
                      : 'Analysing frames… this may take a minute for longer videos.'}
                  </p>
                </div>
              )}
              {result && <ResultPanel result={result} />}
              {!result && !processing && (
                <div className="card" style={{ padding: '48px 24px' }}>
                  <div className="empty-state">
                    <div style={{ fontSize: '3rem', marginBottom: 12 }}>🛣️</div>
                    <h3>No results yet</h3>
                    <p style={{ marginTop: 8, fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                      Select a video file and click Run Video Inspection to begin.
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── History tab ────────────────────────────────────────────────────── */}
      {tab === 'history' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
              {history.length} video inspection{history.length !== 1 ? 's' : ''} on record.
            </p>
            <button className="btn btn-secondary" onClick={loadHistory} id="video-history-refresh-btn">
              🔄 Refresh
            </button>
          </div>

          {histLoading && (
            <div className="loading"><div className="spinner" /><span>Loading history…</span></div>
          )}

          {!histLoading && history.length === 0 && (
            <div className="card">
              <div className="empty-state">
                <div style={{ fontSize: '3rem', marginBottom: 12 }}>📭</div>
                <h3>No video inspections yet</h3>
                <p style={{ marginTop: 8, fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                  Run a video inspection to see results here.
                </p>
              </div>
            </div>
          )}

          {!histLoading && history.map(r => (
            <HistoryRow key={r.inspection_id} r={r} />
          ))}
        </div>
      )}
    </div>
  )
}
