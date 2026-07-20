import { useState } from 'react'
import BuildProgress from './BuildProgress.jsx'
import './ProjectList.css'

function StatusDot({ status }) {
  const map = {
    done: { color: 'var(--success)', label: 'Ready' },
    running: { color: 'var(--accent)', label: 'Building', pulse: true },
    error: { color: 'var(--danger)', label: 'Error' },
    idle: { color: 'var(--muted)', label: 'Idle' },
  }
  const s = map[status] || map.idle
  return (
    <span className={`status-dot ${s.pulse ? 'pulse' : ''}`} style={{ background: s.color }} title={s.label} />
  )
}

function DataBadge({ label, active }) {
  return (
    <span className={`data-badge ${active ? 'active' : ''}`}>{label}</span>
  )
}

function ProjectCard({ project, onDelete, onRefresh, onOpenViewer, isActive }) {
  const [deleting, setDeleting] = useState(false)
  const [expanded, setExpanded] = useState(project.status === 'running')

  const handleDelete = async () => {
    if (!confirm(`Delete project "${project.name}"? This removes all tiles and data.`)) return
    setDeleting(true)
    try {
      await fetch(`/api/projects/${project.name}`, { method: 'DELETE' })
      onRefresh()
    } catch (e) {
      alert('Delete failed: ' + e.message)
      setDeleting(false)
    }
  }

  const bounds = project.bounds
  const boundsStr = bounds
    ? `${bounds.lat_min.toFixed(3)}, ${bounds.lon_min.toFixed(3)} → ${bounds.lat_max.toFixed(3)}, ${bounds.lon_max.toFixed(3)}`
    : '—'

  return (
    <div className={`project-card ${project.status} ${isActive ? 'active-viewer' : ''}`}>
      <div className="card-top">
        <div className="card-identity">
          <StatusDot status={project.status} />
          <span className="card-name">{project.name}</span>
          <span className="card-zoom">z{project.max_zoom}</span>
        </div>
        <div className="card-actions">
          {project.has_viewer && (
            <button
              className={`btn ${isActive ? 'btn-viewer-active' : 'btn-primary'}`}
              onClick={() => onOpenViewer(project)}
            >
              {isActive ? '● Viewing' : '⊞ View Map'}
            </button>
          )}
          {project.status === 'running' && (
            <button className="btn btn-ghost" onClick={() => setExpanded(e => !e)}>
              {expanded ? 'Hide' : 'Show'}
            </button>
          )}
          <button
            className="btn btn-danger"
            onClick={handleDelete}
            disabled={deleting || project.status === 'running'}
          >
            {deleting ? '…' : 'Delete'}
          </button>
        </div>
      </div>

      <div className="card-meta">
        <span className="meta-item">
          <span className="meta-label">Bounds</span>
          <span className="meta-val mono">{boundsStr}</span>
        </span>
      </div>

      <div className="card-badges">
        <DataBadge label="Imagery" active={project.has_imagery} />
        <DataBadge label="Terrain" active={project.has_terrain} />
        <DataBadge label="Buildings" active={project.has_buildings} />
        <DataBadge label="Viewer" active={project.has_viewer} />
      </div>

      {project.status === 'running' && expanded && (
        <div className="card-progress">
          <BuildProgress name={project.name} />
        </div>
      )}

      {project.status === 'error' && (
        <div className="card-error">
          Build failed — check logs or delete and retry
        </div>
      )}
    </div>
  )
}

export default function ProjectList({ projects, loading, onRefresh, onBuild, onOpenViewer, activeViewerName }) {
  if (loading) {
    return (
      <div className="empty-state">
        <div className="spinner" />
        <p>Loading projects...</p>
      </div>
    )
  }

  return (
    <div className="project-list">
      <div className="list-header">
        <div>
          <h1 className="page-title">Projects</h1>
          <p className="page-sub">{projects.length} offline map{projects.length !== 1 ? 's' : ''} built</p>
        </div>
        <button className="btn btn-primary btn-lg" onClick={onBuild}>
          + New Build
        </button>
      </div>

      {projects.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">◈</div>
          <h2>No projects yet</h2>
          <p>Build your first offline 3D map from any coordinates on Earth.</p>
          <button className="btn btn-primary btn-lg" onClick={onBuild}>
            Start building
          </button>
        </div>
      ) : (
        <div className="cards">
          {projects.map(p => (
            <ProjectCard
              key={p.name}
              project={p}
              onDelete={() => {}}
              onRefresh={onRefresh}
              onOpenViewer={onOpenViewer}
              isActive={p.name === activeViewerName}
            />
          ))}
        </div>
      )}
    </div>
  )
}
