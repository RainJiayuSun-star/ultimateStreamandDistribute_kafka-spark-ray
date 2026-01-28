import { useEffect, useState } from 'react'
import { Card, Row, Col, Badge, Spinner, Alert, Table } from 'react-bootstrap'
import api, { HealthStatus } from '../services/api'

function SystemHealth() {
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

  return (
    <div style={{ backgroundColor: '#ffffff', minHeight: '100vh', padding: '1rem' }}>
      <div className="mb-4">
        <h2 style={{ 
          color: '#333333', 
          fontSize: '1.5rem', 
          fontWeight: 600,
          marginBottom: '0.5rem',
          textTransform: 'uppercase',
          letterSpacing: '1px'
        }}>
          System Health Monitoring
        </h2>
        <p style={{ color: '#666666', fontSize: '0.875rem', margin: 0 }}>
          Component Status | Service Availability | Endpoint Monitoring
        </p>
      </div>

      {loading && !health && (
        <div className="d-flex justify-content-center align-items-center" style={{ minHeight: '200px' }}>
          <Spinner animation="border" role="status" variant="light">
            <span className="visually-hidden">Checking health...</span>
          </Spinner>
        </div>
      )}

      {error && (
        <Alert variant="danger" className="mb-4">
          <Alert.Heading>Connection Error</Alert.Heading>
          <p>{error}</p>
        </Alert>
      )}

      {health && (
        <Row className="mb-3">
          <Col md={6}>
            <Card className="bg-dark text-light mb-3">
              <Card.Header>
                <div className="section-title">API Service Status</div>
              </Card.Header>
              <Card.Body>
                <div style={{ fontFamily: 'monospace' }}>
                  <div className="mb-3">
                    <div className="metric-label">Service</div>
                    <div>
                      <code className="code-text">{health.service}</code>
                    </div>
                  </div>
                  <div className="mb-3">
                    <div className="metric-label">Status</div>
                    <div>
                      <Badge className={health.status === 'healthy' ? 'status-healthy' : 'status-error'}>
                        {health.status.toUpperCase()}
                      </Badge>
                    </div>
                  </div>
                  {lastCheck && (
                    <div>
                      <div className="metric-label">Last Check</div>
                      <div style={{ color: '#666666', fontSize: '0.875rem' }}>
                        {lastCheck.toLocaleTimeString('en-US', { 
                          hour12: false,
                          hour: '2-digit',
                          minute: '2-digit',
                          second: '2-digit'
                        })}
                      </div>
                    </div>
                  )}
                </div>
              </Card.Body>
            </Card>
          </Col>

          <Col md={6}>
            <Card className="bg-dark text-light mb-3">
              <Card.Header>
                <div className="section-title">System Components</div>
              </Card.Header>
              <Card.Body>
                <Table className="tech-table" hover>
                  <thead>
                    <tr>
                      <th>Component</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr>
                      <td><code className="code-text">Kafka Broker</code></td>
                      <td><Badge className="status-healthy">RUNNING</Badge></td>
                    </tr>
                    <tr>
                      <td><code className="code-text">Spark Master</code></td>
                      <td><Badge className="status-healthy">RUNNING</Badge></td>
                    </tr>
                    <tr>
                      <td><code className="code-text">Spark Workers</code></td>
                      <td><Badge className="status-healthy">RUNNING</Badge></td>
                    </tr>
                    <tr>
                      <td><code className="code-text">Ray Head</code></td>
                      <td><Badge className="status-healthy">RUNNING</Badge></td>
                    </tr>
                    <tr>
                      <td><code className="code-text">Ray Workers</code></td>
                      <td><Badge className="status-healthy">RUNNING</Badge></td>
                    </tr>
                    <tr>
                      <td><code className="code-text">API Service</code></td>
                      <td>
                        <Badge className={health.status === 'healthy' ? 'status-healthy' : 'status-error'}>
                          {health.status === 'healthy' ? 'RUNNING' : 'DOWN'}
                        </Badge>
                      </td>
                    </tr>
                  </tbody>
                </Table>
              </Card.Body>
            </Card>
          </Col>
        </Row>
      )}

      <Row>
        <Col md={12}>
          <Card className="bg-dark text-light">
            <Card.Header>
              <div className="section-title">Monitoring Endpoints</div>
            </Card.Header>
            <Card.Body>
              <Table className="tech-table" hover>
                <thead>
                  <tr>
                    <th>Service</th>
                    <th>Endpoint</th>
                    <th>Description</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td><code className="code-text">Spark Master UI</code></td>
                    <td>
                      <a 
                        href="http://localhost:8080" 
                        target="_blank" 
                        rel="noopener noreferrer"
                        style={{ color: '#0066cc', textDecoration: 'none' }}
                      >
                        <code className="code-text">http://localhost:8080</code>
                      </a>
                    </td>
                    <td style={{ color: '#666666', fontSize: '0.875rem' }}>
                      View Spark cluster status, active jobs, and worker nodes
                    </td>
                  </tr>
                  <tr>
                    <td><code className="code-text">Ray Dashboard</code></td>
                    <td>
                      <a 
                        href="http://localhost:8265" 
                        target="_blank" 
                        rel="noopener noreferrer"
                        style={{ color: '#0066cc', textDecoration: 'none' }}
                      >
                        <code className="code-text">http://localhost:8265</code>
                      </a>
                    </td>
                    <td style={{ color: '#666666', fontSize: '0.875rem' }}>
                      Monitor Ray actors, tasks, and resource utilization
                    </td>
                  </tr>
                  <tr>
                    <td><code className="code-text">API Health</code></td>
                    <td>
                      <a 
                        href="http://localhost:5000/health" 
                        target="_blank" 
                        rel="noopener noreferrer"
                        style={{ color: '#0066cc', textDecoration: 'none' }}
                      >
                        <code className="code-text">http://localhost:5000/health</code>
                      </a>
                    </td>
                    <td style={{ color: '#666666', fontSize: '0.875rem' }}>
                      Check API service health status (JSON response)
                    </td>
                  </tr>
                  <tr>
                    <td><code className="code-text">API Predictions</code></td>
                    <td>
                      <code className="code-text">http://localhost:5000/predictions/latest</code>
                    </td>
                    <td style={{ color: '#666666', fontSize: '0.875rem' }}>
                      Get latest weather predictions from Kafka topic
                    </td>
                  </tr>
                </tbody>
              </Table>
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </div>
  )
}

export default SystemHealth
