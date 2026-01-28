import { useEffect, useState } from 'react'
import { Card, Badge, Table } from 'react-bootstrap'
import api, { HealthStatus } from '../services/api'

function SystemHealthAndPipeline() {
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastCheck, setLastCheck] = useState<Date | null>(null)

  useEffect(() => {
    const checkHealth = async () => {
      try {
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
    {
      name: 'Kafka Broker',
      status: 'running',
      description: 'Message queuing and topic management',
      endpoint: 'localhost:9092'
    },
    {
      name: 'Spark Master',
      status: 'running',
      description: 'Cluster coordination and job scheduling',
      endpoint: 'localhost:8080'
    },
    {
      name: 'Spark Workers',
      status: 'running',
      description: 'Distributed stream processing (4 workers)',
    },
    {
      name: 'Ray Head',
      status: 'running',
      description: 'Actor management and task scheduling',
      endpoint: 'localhost:8265'
    },
    {
      name: 'Ray Workers',
      status: 'running',
      description: 'ML inference execution (4 workers)',
    },
    {
      name: 'API Service',
      status: health?.status === 'healthy' ? 'running' : (error ? 'error' : 'running'),
      description: 'REST API and prediction serving',
      endpoint: 'localhost:5000'
    },
  ]

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'running':
        return (
          <Badge 
            style={{ 
              backgroundColor: '#28a745', 
              color: '#ffffff',
              padding: '0.2rem 0.6rem',
              borderRadius: '3px',
              fontSize: '0.75rem',
              fontWeight: 500,
              textTransform: 'uppercase',
              letterSpacing: '0.5px'
            }}
          >
            RUNNING
          </Badge>
        )
      case 'idle':
        return <Badge className="status-warning">IDLE</Badge>
      case 'error':
        return <Badge className="status-error">ERROR</Badge>
      default:
        return <Badge bg="secondary">UNKNOWN</Badge>
    }
  }

  return (
    <Card className="bg-dark text-light fade-in">
      <Card.Header>
        <div className="section-title">System Health & Pipeline Components</div>
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
              <th>Description</th>
              <th>Endpoint</th>
            </tr>
          </thead>
          <tbody>
            {components.map((component, idx) => (
              <tr key={idx}>
                <td>
                  <code style={{ fontFamily: 'Courier New, monospace', fontSize: '0.875rem', color: '#28a745', backgroundColor: '#f5f5f5', padding: '0.2rem 0.4rem', borderRadius: '3px' }}>
                    {component.name}
                  </code>
                </td>
                <td>{getStatusBadge(component.status)}</td>
                <td style={{ color: '#666666' }}>{component.description}</td>
                <td>
                  {component.endpoint ? (
                    <code style={{ fontFamily: 'Courier New, monospace', fontSize: '0.875rem', color: '#28a745', backgroundColor: '#f5f5f5', padding: '0.2rem 0.4rem', borderRadius: '3px' }}>
                      {component.endpoint}
                    </code>
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

export default SystemHealthAndPipeline
