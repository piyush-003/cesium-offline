import { useState, useEffect } from 'react'
import Header from './components/Header.jsx'
import ProjectList from './components/ProjectList.jsx'
import BuildPanel from './components/BuildPanel.jsx'
import CesiumViewer from './components/CesiumViewer.jsx'
import './App.css'

export default function App() {
  const [view, setView] = useState('projects') // 'projects' | 'build'
  const [projects, setProjects] = useState([])
  const [loading, setLoading] = useState(true)
  const [activeViewer, setActiveViewer] = useState(null) // project object or null

  const fetchProjects = async () => {
    try {
      const res = await fetch('/api/projects')
      const data = await res.json()
      setProjects(data)

      // If viewer is open, keep its data fresh
      if (activeViewer) {
        const updated = data.find(p => p.name === activeViewer.name)
        if (updated) setActiveViewer(updated)
      }
    } catch (e) {
      console.error('Failed to fetch projects', e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchProjects()
    const interval = setInterval(fetchProjects, 3000)
    return () => clearInterval(interval)
  }, [])

  const openViewer = (project) => {
    setActiveViewer(project)
    setView('projects')
  }

  const closeViewer = () => setActiveViewer(null)

  const showSplit = activeViewer !== null && view === 'projects'

  return (
    <div className="app">
      <Header view={view} setView={setView} onLogoClick={closeViewer} />
      <div className={`app-body ${showSplit ? 'split' : ''}`}>
        <main className={`main ${showSplit ? 'main-split' : ''}`}>
          {view === 'projects' ? (
            <ProjectList
              projects={projects}
              loading={loading}
              onRefresh={fetchProjects}
              onBuild={() => setView('build')}
              onOpenViewer={openViewer}
              activeViewerName={activeViewer?.name}
            />
          ) : (
            <BuildPanel
              onDone={(project) => {
                fetchProjects()
                setView('projects')
                if (project) openViewer(project)
              }}
              onCancel={() => setView('projects')}
            />
          )}
        </main>

        {showSplit && (
          <div className="viewer-pane">
            <CesiumViewer project={activeViewer} onClose={closeViewer} />
          </div>
        )}
      </div>
    </div>
  )
}
