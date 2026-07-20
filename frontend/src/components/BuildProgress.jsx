import { useState, useEffect } from 'react'
import './BuildProgress.css'

export default function BuildProgress({ name }) {
  const [status, setStatus] = useState(null)

  useEffect(() => {
    const poll = async () => {
      try {
        const res = await fetch(`/api/projects/${name}/status`)
        const data = await res.json()
        setStatus(data)
      } catch (e) {}
    }
    poll()
    const interval = setInterval(poll, 1500)
    return () => clearInterval(interval)
  }, [name])

  if (!status) return <div className="bp-loading">Connecting...</div>

  const pct = status.progress || 0

  const STEPS = [
    'Download satellite imagery',
    'Download DEM elevation',
    'Download OSM buildings',
    'Generate terrain tiles',
    'Generate viewer HTML',
  ]

  return (
    <div className="build-progress">
      <div className="bp-bar-wrap">
        <div className="bp-bar" style={{ width: `${pct}%` }} />
      </div>
      <div className="bp-row">
        <span className="bp-step">{status.step}</span>
        <span className="bp-pct">{pct}%</span>
      </div>
      <div className="bp-msg">{status.message}</div>
      {status.error && <div className="bp-error">{status.error}</div>}

      <div className="bp-steps">
        {STEPS.map((s, i) => {
          const done = i < status.step_number - 1
          const current = s === status.step
          return (
            <div key={s} className={`bp-step-item ${done ? 'done' : ''} ${current ? 'current' : ''}`}>
              <span className="bp-step-dot">{done ? '✓' : current ? '●' : '○'}</span>
              <span className="bp-step-label">{s}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
