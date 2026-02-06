import { Routes, Route, Link, useLocation } from 'react-router-dom'
import RunsList from './pages/RunsList'
import RunDetail from './pages/RunDetail'
import StrategyDetail from './pages/StrategyDetail'
import NewRun from './pages/NewRun'

function App() {
  const location = useLocation()

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white shadow-sm border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex justify-between items-center">
            <Link to="/" className="text-2xl font-bold text-gray-900 hover:text-gray-700">
              Darwin Evolution Viewer
            </Link>
            {location.pathname === '/' && (
              <Link
                to="/new-run"
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 font-medium"
              >
                + New Run
              </Link>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6">
        <Routes>
          <Route path="/" element={<RunsList />} />
          <Route path="/new-run" element={<NewRun />} />
          <Route path="/runs/:runId" element={<RunDetail />} />
          <Route path="/runs/:runId/strategy/:graphId" element={<StrategyDetail />} />
        </Routes>
      </main>
    </div>
  )
}

export default App
