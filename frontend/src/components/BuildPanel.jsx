import { useState, useEffect, useRef } from 'react'
import BuildProgress from './BuildProgress.jsx'
import './BuildPanel.css'

const PRESETS = [
  { label: 'Kashmir Valley', bounds: [34.08154, 73.58274, 34.52480, 74.13570] },
  { label: 'Delhi Center', bounds: [28.6215, 77.2067, 28.6415, 77.2267] },
  { label: 'Kathmandu', bounds: [27.665, 85.27, 27.745, 85.38] },
  { label: 'Ladakh', bounds: [34.1, 77.5, 34.5, 78.0] },
]

function parseBoundsString(str) {
  const parts = str.split(',').map(s => parseFloat(s.trim()))
  if (parts.length === 4 && parts.every(n => !isNaN(n))) {
    const [lat_min, lon_min, lat_max, lon_max] = parts
    if (lat_min < lat_max && lon_min < lon_max) return [lat_min, lon_min, lat_max, lon_max]
  }
  return null
}

function MapSelector({ bounds, onChange }) {
  const mapRef = useRef(null)
  const mapInstanceRef = useRef(null)
  const rectRef = useRef(null)
  const drawModeRef = useRef(false)

  useEffect(() => {
    if (mapInstanceRef.current || typeof window === 'undefined') return
    import('leaflet').then(L => {
      const map = L.map(mapRef.current, {
        center: [28.6, 77.2],
        zoom: 4,
        zoomControl: true,
        dragging: true,
        scrollWheelZoom: true,
      })
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '© OpenStreetMap',
        maxZoom: 18,
      }).addTo(map)
      mapInstanceRef.current = { map, L }

      let startLatLng = null

      // Only draw when in draw mode (Shift held or draw button active)
      map.on('mousedown', (e) => {
        if (!drawModeRef.current) return
        if (e.originalEvent.button !== 0) return
        e.originalEvent.preventDefault()
        startLatLng = e.latlng
        map.dragging.disable()
      })

      map.on('mousemove', (e) => {
        if (!drawModeRef.current || !startLatLng) return
        const b = toBounds(startLatLng, e.latlng)
        drawRect(b, map, L)
      })

      map.on('mouseup', (e) => {
        if (!drawModeRef.current || !startLatLng) return
        map.dragging.enable()
        const b = toBounds(startLatLng, e.latlng)
        if (Math.abs(b[2] - b[0]) > 0.001 && Math.abs(b[3] - b[1]) > 0.001) {
          drawRect(b, map, L)
          onChange(b)
        }
        startLatLng = null
      })
    })
    return () => {
      if (mapInstanceRef.current) {
        mapInstanceRef.current.map.remove()
        mapInstanceRef.current = null
      }
    }
  }, [])

  function toBounds(a, b) {
    return [
      Math.min(a.lat, b.lat), Math.min(a.lng, b.lng),
      Math.max(a.lat, b.lat), Math.max(a.lng, b.lng),
    ]
  }

  function drawRect(b, map, L) {
    if (rectRef.current) rectRef.current.remove()
    rectRef.current = L.rectangle(
      [[b[0], b[1]], [b[2], b[3]]],
      { color: '#4f8ef7', weight: 2, fillColor: '#4f8ef7', fillOpacity: 0.12 }
    ).addTo(map)
  }

  useEffect(() => {
    if (!bounds || !mapInstanceRef.current) return
    const { map, L } = mapInstanceRef.current
    if (rectRef.current) rectRef.current.remove()
    rectRef.current = L.rectangle(
      [[bounds[0], bounds[1]], [bounds[2], bounds[3]]],
      { color: '#4f8ef7', weight: 2, fillColor: '#4f8ef7', fillOpacity: 0.12 }
    ).addTo(map)
    map.fitBounds([[bounds[0], bounds[1]], [bounds[2], bounds[3]]], { padding: [40, 40] })
  }, [bounds])

  const enterDrawMode = () => {
    drawModeRef.current = true
    if (mapInstanceRef.current) {
      mapInstanceRef.current.map.dragging.disable()
      mapInstanceRef.current.map.getContainer().style.cursor = 'crosshair'
    }
  }

  const exitDrawMode = () => {
    drawModeRef.current = false
    if (mapInstanceRef.current) {
      mapInstanceRef.current.map.dragging.enable()
      mapInstanceRef.current.map.getContainer().style.cursor = ''
    }
  }

  return (
    <div className="map-outer">
      <div className="map-toolbar">
        <span className="map-tip">🖐 Drag to pan &nbsp;|&nbsp; 🔲 Hold button below to draw area</span>
        <button
          className="draw-btn"
          onMouseDown={enterDrawMode}
          onMouseUp={exitDrawMode}
          onMouseLeave={exitDrawMode}
        >
          ✏ Draw Area
        </button>
      </div>
      <div className="map-wrap">
        <div ref={mapRef} className="map" />
      </div>
    </div>
  )
}

export default function BuildPanel({ onDone, onCancel }) {
  const [name, setName] = useState('')
  const [bounds, setBounds] = useState(null)
  const [coordInput, setCoordInput] = useState('')
  const [coordError, setCoordError] = useState('')
  const [maxZoom, setMaxZoom] = useState(14)
  const [skipImagery, setSkipImagery] = useState(false)
  const [skipDem, setSkipDem] = useState(false)
  const [skipBuildings, setSkipBuildings] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [buildName, setBuildName] = useState(null)
  const [error, setError] = useState('')

  const applyPreset = (preset) => {
    setBounds(preset.bounds)
    setCoordInput(preset.bounds.join(', '))
    setCoordError('')
    if (!name) setName(preset.label.toLowerCase().replace(/\s+/g, '_'))
  }

  const handleCoordInput = (val) => {
    setCoordInput(val)
    setCoordError('')
    const parsed = parseBoundsString(val)
    if (parsed) {
      setBounds(parsed)
    } else if (val.trim()) {
      setCoordError('Format: lat_min, lon_min, lat_max, lon_max')
    }
  }

  const handleMapChange = (b) => {
    setBounds(b)
    setCoordInput(b.map(n => n.toFixed(5)).join(', '))
    setCoordError('')
  }

  const handleSubmit = async () => {
    setError('')
    if (!name.trim()) return setError('Project name is required')
    if (!bounds) return setError('Select an area on the map or enter coordinates')
    if (bounds[2] - bounds[0] < 0.001 || bounds[3] - bounds[1] < 0.001)
      return setError('Area too small')
    setSubmitting(true)
    try {
      const res = await fetch('/api/projects', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: name.trim().toLowerCase().replace(/\s+/g, '_'),
          lat_min: bounds[0], lon_min: bounds[1],
          lat_max: bounds[2], lon_max: bounds[3],
          max_zoom: maxZoom,
          skip_imagery: skipImagery,
          skip_dem: skipDem,
          skip_buildings: skipBuildings,
        }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Build failed to start')
      setBuildName(data.name)
    } catch (e) {
      setError(e.message)
      setSubmitting(false)
    }
  }

  if (buildName) {
    return (
      <div className="build-panel">
        <div className="build-running">
          <div className="running-header">
            <div className="running-icon">⬡</div>
            <div>
              <h2>Building <span className="mono">{buildName}</span></h2>
              <p className="running-sub">Running in background — switch to Projects to monitor</p>
            </div>
          </div>
          <BuildProgress name={buildName} />
          <div className="running-actions">
            <button className="btn btn-ghost" onClick={onCancel}>← Back to projects</button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="build-panel">
      <div className="build-header">
        <div>
          <h1 className="page-title">New Build</h1>
          <p className="page-sub">Select an area and configure your offline 3D map</p>
        </div>
        <button className="btn btn-ghost" onClick={onCancel}>Cancel</button>
      </div>

      <div className="build-layout">
        <div className="build-map-col">
          <div className="section-label">Area of Interest</div>
          <div className="presets">
            {PRESETS.map(p => (
              <button key={p.label} className="preset-btn" onClick={() => applyPreset(p)}>{p.label}</button>
            ))}
          </div>
          <div className="coord-input-wrap">
            <label className="coord-label">
              Paste coordinates
              <span className="coord-format">lat_min, lon_min, lat_max, lon_max</span>
            </label>
            <input
              type="text"
              className={`coord-input ${coordError ? 'has-error' : bounds && coordInput ? 'has-valid' : ''}`}
              value={coordInput}
              onChange={e => handleCoordInput(e.target.value)}
              placeholder="34.08154, 73.58274, 34.52480, 74.13570"
            />
            {coordError && <span className="coord-error">{coordError}</span>}
            {bounds && !coordError && coordInput && <span className="coord-ok">✓ Valid bounds</span>}
          </div>
          <MapSelector bounds={bounds} onChange={handleMapChange} />
        </div>

        <div className="build-form-col">
          <div className="form-section">
            <div className="section-label">Project</div>
            <div className="field">
              <label>Name</label>
              <input
                type="text"
                value={name}
                onChange={e => setName(e.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, ''))}
                placeholder="e.g. kashmir_small"
              />
              <span className="field-hint">Lowercase, numbers, hyphens only</span>
            </div>
          </div>

          <div className="form-section">
            <div className="section-label">Imagery zoom</div>
            <div className="field">
              <div className="zoom-row">
                <input
                  type="range" min={10} max={20} value={maxZoom}
                  onChange={e => setMaxZoom(Number(e.target.value))}
                  className="zoom-slider"
                />
                <span className="zoom-val mono">z{maxZoom}</span>
              </div>
              <div className="zoom-labels">
                <span>z10 overview</span>
                <span>z14 roads</span>
                <span>z16 streets</span>
                <span>z20 detail</span>
              </div>
              <div className="zoom-size-hint">
                ~{maxZoom <= 12 ? 'a few MB' : maxZoom <= 14 ? '10–80 MB' : maxZoom <= 16 ? '100–500 MB' : '1–5 GB'} of imagery
              </div>
            </div>
          </div>

          <div className="form-section">
            <div className="section-label">Skip steps (reuse existing data)</div>
            <div className="toggles">
              <label className="toggle">
                <input type="checkbox" checked={skipImagery} onChange={e => setSkipImagery(e.target.checked)} />
                <span>Skip imagery download</span>
              </label>
              <label className="toggle">
                <input type="checkbox" checked={skipDem} onChange={e => setSkipDem(e.target.checked)} />
                <span>Skip DEM download</span>
              </label>
              <label className="toggle">
                <input type="checkbox" checked={skipBuildings} onChange={e => setSkipBuildings(e.target.checked)} />
                <span>Skip OSM buildings</span>
              </label>
            </div>
          </div>

          {error && <div className="form-error">{error}</div>}

          <button className="btn btn-primary btn-lg btn-full" onClick={handleSubmit} disabled={submitting}>
            {submitting ? 'Starting...' : '▶ Start Build'}
          </button>
        </div>
      </div>
    </div>
  )
}
