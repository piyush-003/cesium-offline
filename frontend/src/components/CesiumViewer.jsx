import { useEffect, useRef, useState } from 'react'
import './CesiumViewer.css'

export default function CesiumViewer({ project, onClose }) {
  const [fullscreen, setFullscreen] = useState(false)
  const [loading, setLoading] = useState(true)
  const iframeRef = useRef(null)

  // The Node.js server runs on 8088 by default
  const viewerUrl = `http://localhost:8088/index.html`

  useEffect(() => {
    setLoading(true)
  }, [project])

  return (
    <div className={`cesium-viewer-panel ${fullscreen ? 'fullscreen' : ''}`}>
      <div className="viewer-toolbar">
        <div className="viewer-title">
          <span className="viewer-dot" />
          <span className="viewer-name">{project.name}</span>
          <span className="viewer-badge">z{project.max_zoom}</span>
          <span className="viewer-sep">·</span>
          <span className="viewer-meta">
            {project.bounds
              ? `${project.bounds.lat_min.toFixed(3)}, ${project.bounds.lon_min.toFixed(3)} → ${project.bounds.lat_max.toFixed(3)}, ${project.bounds.lon_max.toFixed(3)}`
              : ''}
          </span>
        </div>
        <div className="viewer-controls">
          <button
            className="viewer-btn"
            onClick={() => setFullscreen(f => !f)}
            title={fullscreen ? 'Exit fullscreen' : 'Fullscreen'}
          >
            {fullscreen ? '⊡' : '⊞'}
          </button>
          <a
            href={viewerUrl}
            target="_blank"
            rel="noreferrer"
            className="viewer-btn"
            title="Open in new tab"
          >
            ↗
          </a>
          <button
            className="viewer-btn viewer-btn-close"
            onClick={onClose}
            title="Close viewer"
          >
            ✕
          </button>
        </div>
      </div>

      <div className="viewer-frame-wrap">
        {loading && (
          <div className="viewer-loading">
            <div className="viewer-spinner" />
            <span>Starting viewer server…</span>
            <span className="viewer-loading-sub">
              Make sure <code>python3 run.py --name {project.name} --serve-only</code> is running
            </span>
          </div>
        )}
        <iframe
          ref={iframeRef}
          src={viewerUrl}
          className="viewer-frame"
          title="Cesium 3D Viewer"
          onLoad={() => setLoading(false)}
          onError={() => setLoading(false)}
          allow="fullscreen"
        />
      </div>
    </div>
  )
}
