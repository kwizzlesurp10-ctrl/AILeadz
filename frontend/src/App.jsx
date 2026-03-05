import { useState, useEffect, useRef, useCallback } from 'react'
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { Menu } from 'lucide-react'
import Sidebar from './components/Sidebar'
import Dashboard from './pages/Dashboard'
import AgentDetail from './pages/AgentDetail'
import WorkView from './pages/WorkView'
import LearningView from './pages/LearningView'
import Leaderboard from './pages/Leaderboard'
import Artifacts from './pages/Artifacts'
import { useWebSocket } from './hooks/useWebSocket'
import { fetchAgents, fetchHiddenAgents, saveHiddenAgents, fetchDisplayNames } from './api'
import { DisplayNamesContext } from './DisplayNamesContext'

function App() {
  const [agents, setAgents] = useState([])
  const [selectedAgent, setSelectedAgent] = useState(null)
  const [hiddenAgents, setHiddenAgents] = useState(new Set())
  const [displayNames, setDisplayNames] = useState({})
  const { lastMessage, connectionStatus } = useWebSocket()
  const hasAutoSelected = useRef(false)

  // Auto-select first VISIBLE agent once both agents and hiddenAgents are loaded
  useEffect(() => {
    if (hasAutoSelected.current) return
    const firstVisible = agents.find(a => !hiddenAgents.has(a.signature))
    if (firstVisible) {
      setSelectedAgent(firstVisible.signature)
      hasAutoSelected.current = true
    }
  }, [agents, hiddenAgents])

  // Fetch hidden agents on mount
  useEffect(() => {
    fetchHiddenAgents()
      .then(data => setHiddenAgents(new Set(data.hidden || [])))
      .catch(err => console.error('Error fetching hidden agents:', err))
  }, [])

  // Fetch display names on mount
  useEffect(() => {
    fetchDisplayNames()
      .then(data => setDisplayNames(data || {}))
      .catch(() => {})
  }, [])

  // Fetch agents on mount
  useEffect(() => {
    fetchAgentsData()
    const interval = setInterval(fetchAgentsData, 5000)
    return () => clearInterval(interval)
  }, [])

  // Handle WebSocket messages
  useEffect(() => {
    if (lastMessage) handleWebSocketMessage(lastMessage)
  }, [lastMessage])

  const fetchAgentsData = async () => {
    try {
      const data = await fetchAgents()
      setAgents(data.agents || [])
    } catch (error) {
      console.error('Error fetching agents:', error)
    }
  }

  const handleWebSocketMessage = (message) => {
    console.log('WebSocket message:', message)

    if (message.type === 'balance_update' || message.type === 'activity_update') {
      // Refresh agents when updates come in
      fetchAgents()
    }
  }

  const updateHiddenAgents = useCallback(async (newHiddenSet) => {
    setHiddenAgents(newHiddenSet)
    try {
      await saveHiddenAgents(Array.from(newHiddenSet))
    } catch (error) {
      console.error('Error saving hidden agents:', error)
    }
  }, [])

  const visibleAgents = agents.filter(a => !hiddenAgents.has(a.signature))
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <DisplayNamesContext.Provider value={displayNames}>
    <Router basename={import.meta.env.BASE_URL}>
      <div className="flex h-screen bg-gray-50">
        {sidebarOpen && (
          <div
            className="fixed inset-0 bg-black/50 z-30 md:hidden"
            onClick={() => setSidebarOpen(false)}
            aria-hidden="true"
          />
        )}
        <Sidebar
          agents={visibleAgents}
          allAgents={agents}
          hiddenAgents={hiddenAgents}
          onUpdateHiddenAgents={updateHiddenAgents}
          selectedAgent={selectedAgent}
          onSelectAgent={setSelectedAgent}
          connectionStatus={connectionStatus}
          isOpen={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
        />

        <div className="flex flex-1 flex-col min-w-0">
          <header className="flex items-center gap-3 p-3 border-b border-gray-200 bg-white md:hidden shrink-0">
            <button
              type="button"
              onClick={() => setSidebarOpen(true)}
              className="p-2 -ml-1 rounded-lg text-gray-600 hover:bg-gray-100"
              aria-label="Open menu"
            >
              <Menu className="w-6 h-6" />
            </button>
            <span className="font-semibold text-gray-900 truncate">LiveBench</span>
          </header>
        <main className="flex-1 overflow-y-auto min-h-0">
          <Routes>
            <Route path="/" element={
              <Leaderboard hiddenAgents={hiddenAgents} />
            } />
            <Route path="/dashboard" element={
              <Dashboard
                agents={visibleAgents}
                selectedAgent={selectedAgent}
              />
            } />
            <Route path="/agent/:signature" element={
              <AgentDetail />
            } />
            <Route path="/artifacts" element={
              <Artifacts />
            } />
            <Route path="/work" element={
              <WorkView
                agents={visibleAgents}
                selectedAgent={selectedAgent}
              />
            } />
            <Route path="/learning" element={
              <LearningView
                agents={visibleAgents}
                selectedAgent={selectedAgent}
              />
            } />
          </Routes>
        </main>
        </div>
      </div>
    </Router>
    </DisplayNamesContext.Provider>
  )
}

export default App
