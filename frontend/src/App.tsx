import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { Container } from 'react-bootstrap'
import Navigation from './components/Navigation'
import Dashboard from './pages/Dashboard'
import Architecture from './pages/Architecture'
import SystemHealth from './pages/SystemHealth'
import './App.css'

function App() {
  return (
    <Router
      future={{
        v7_startTransition: true,
        v7_relativeSplatPath: true,
      }}
    >
      <div className="App">
        <Navigation />
        <Container fluid style={{ padding: '0', maxWidth: '100%' }}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/architecture" element={<Architecture />} />
            <Route path="/health" element={<SystemHealth />} />
          </Routes>
        </Container>
      </div>
    </Router>
  )
}

export default App
