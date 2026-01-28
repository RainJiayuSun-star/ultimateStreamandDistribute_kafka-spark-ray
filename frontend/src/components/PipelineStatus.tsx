import { Card, Table, Badge } from 'react-bootstrap'

interface PipelineComponent {
  name: string
  status: 'running' | 'idle' | 'error'
  description: string
  endpoint?: string
}

function PipelineStatus() {
  const components: PipelineComponent[] = [
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
      status: 'running',
      description: 'REST API and prediction serving',
      endpoint: 'localhost:5000'
    },
  ]

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'running':
        return <Badge bg="success" className="status-healthy">RUNNING</Badge>
      case 'idle':
        return <Badge bg="warning" className="status-warning">IDLE</Badge>
      case 'error':
        return <Badge bg="danger" className="status-error">ERROR</Badge>
      default:
        return <Badge bg="secondary">UNKNOWN</Badge>
    }
  }

  return (
    <Card className="bg-dark text-light fade-in">
      <Card.Header>
        <div className="section-title">Pipeline Components</div>
      </Card.Header>
      <Card.Body>
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
                  <code className="code-text">{component.name}</code>
                </td>
                <td>{getStatusBadge(component.status)}</td>
                <td style={{ color: '#888' }}>{component.description}</td>
                <td>
                  {component.endpoint ? (
                    <code className="code-text">{component.endpoint}</code>
                  ) : (
                    <span style={{ color: '#555' }}>—</span>
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

export default PipelineStatus
