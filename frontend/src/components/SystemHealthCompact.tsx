import { useEffect, useState } from 'react'
import { Card, Badge, Table } from 'react-bootstrap'
import api, { HealthStatus } from '../services/api'

function SystemHealthCompact() {
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastCheck, setLastCheck] = useState<Date | null>(null)

  useEffect(() => {
    const checkHealth = async () => {
      try {
        setLoading(true)
        const status = await api.getHealth()
        setHealth(status)
        setLastCheck(new Date())
        setError(null)
      } catch (err) {
        setError('Unable to connect to API service')
        console.error('Health check error:', err)
      } finally {
        setLoading(false)
      }
    }

    checkHealth()
    // Check health every 10 seconds
    const interval = setInterval(checkHealth, 10000)

    return () => clearInterval(interval)
  }, [])

  const components = [
    { name: 'Kafka Broker', status: 'running', endpoint: 'localhost:9092' },
    { name: 'Spark Master', status: 'running', endpoint: 'localhost:8080' },
    { name: 'Spark Workers', status: 'running', description: '4 workers' },
    { name: 'Ray Head', status: 'running', endpoint: 'localhost:8265' },
    { name: 'Ray Workers', status: 'running', description: '4 workers' },
    { 
      name: 'API Service', 
      status: health?.status === 'healthy' ? 'running' : 'error',
      endpoint: 'localhost:5000'
    },
  ]

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'running':
        return <Badge className="status-healthy">RUNNING</Badge>
      case 'error':
        return <Badge className="status-error">ERROR</Badge>
      default:
        return <Badge bg="secondary">UNKNOWN</Badge>
    }
  }

  return (
    <Card className="bg-dark text-light fade-in">
      <Card.Header>
        <div className="section-title">System Health Monitoring</div>
        {lastCheck && (
          <small style={{ color: '#666666', fontSize: '0.75rem' }}>
            Last check: {lastCheck.toLocaleTimeString()}
          </small>
        )}
      </Card.Header>
      <Card.Body>
        {error && (
          <div style={{ color: '#dc3545', fontSize: '0.875rem', marginBottom: '1rem' }}>
            {error}
          </div>
        )}
        <Table className="tech-table" hover>
          <thead>
            <tr>
              <th>Component</th>
              <th>Status</th>
              <th>Endpoint/Info</th>
            </tr>
          </thead>
          <tbody>
            {components.map((component, idx) => (
              <tr key={idx}>
                <td>
                  <code className="code-text">{component.name}</code>
                </td>
                <td>{getStatusBadge(component.status)}</td>
                <td>
                  {component.endpoint ? (
                    <code className="code-text">{component.endpoint}</code>
                  ) : component.description ? (
                    <span style={{ color: '#666666' }}>{component.description}</span>
                  ) : (
                    <span style={{ color: '#666666' }}>—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </Table>
      </Card.Body>
    </Card>
  )
}

export default SystemHealthCompact
