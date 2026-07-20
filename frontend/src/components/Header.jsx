import './Header.css'

export default function Header({ view, setView }) {
  return (
    <header className="header">
      <div className="header-left">
        <div className="logo">
          <span className="logo-icon">◈</span>
          <span className="logo-text">CesiumOffline</span>
        </div>
        <span className="logo-sub">3D Map Builder</span>
      </div>
      <nav className="header-nav">
        <button
          className={`nav-btn ${view === 'projects' ? 'active' : ''}`}
          onClick={() => setView('projects')}
        >
          Projects
        </button>
        <button
          className={`nav-btn ${view === 'build' ? 'active' : ''}`}
          onClick={() => setView('build')}
        >
          + New Build
        </button>
      </nav>
    </header>
  )
}
