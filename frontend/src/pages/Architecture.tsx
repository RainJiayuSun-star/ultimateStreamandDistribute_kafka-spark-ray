import { Card, Row, Col, Table } from 'react-bootstrap'

function Architecture() {
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
          System Architecture
        </h2>
        <p style={{ color: '#666666', fontSize: '0.875rem', margin: 0 }}>
          Lambda Architecture Implementation | Distributed Stream Processing
        </p>
      </div>

      <Row className="mb-3">
        <Col md={12}>
          <Card className="bg-dark text-light mb-3">
            <Card.Header>
              <div className="section-title">Architecture Overview</div>
            </Card.Header>
            <Card.Body>
              <p style={{ color: '#666666', fontSize: '0.875rem', lineHeight: '1.8' }}>
                This system implements a <strong style={{ color: '#333333' }}>Lambda Architecture</strong> pattern 
                for real-time weather forecasting, integrating three distributed systems: 
                <code className="code-text">Kafka</code>, <code className="code-text">Spark</code>, and 
                <code className="code-text">Ray</code>.
              </p>
            </Card.Body>
          </Card>
        </Col>
      </Row>

      <Row className="mb-3">
        <Col md={12}>
          <Card className="bg-dark text-light">
            <Card.Header>
              <div className="section-title">Data Pipeline Flow</div>
            </Card.Header>
            <Card.Body>
              <div style={{ fontFamily: 'monospace', fontSize: '0.875rem' }}>
                <div style={{ 
                  padding: '1rem', 
                  backgroundColor: '#f8f9fa', 
                  borderLeft: '3px solid #0066cc',
                  marginBottom: '1rem',
                  borderRadius: '4px'
                }}>
                  <div style={{ color: '#0066cc', marginBottom: '0.5rem', fontWeight: 600 }}>
                    [1] DATA INGESTION LAYER
                  </div>
                  <div style={{ color: '#666666', marginBottom: '0.5rem' }}>
                    Component: <code className="code-text">Kafka Broker</code>
                  </div>
                  <div style={{ color: '#333333', fontSize: '0.8rem', lineHeight: '1.6' }}>
                    Weather data collected from Open-Meteo API (15s interval)<br/>
                    Published to topic: <code className="code-text">weather-raw</code> (4 partitions)<br/>
                    Format: JSON | Schema: station_id, timestamp, temperature, humidity, pressure, wind_speed
                  </div>
                </div>

                <div style={{ textAlign: 'center', color: '#666666', margin: '0.5rem 0', fontSize: '1.2rem' }}>
                  ↓
                </div>

                <div style={{ 
                  padding: '1rem', 
                  backgroundColor: '#f8f9fa', 
                  borderLeft: '3px solid #28a745',
                  marginBottom: '1rem',
                  borderRadius: '4px'
                }}>
                  <div style={{ color: '#28a745', marginBottom: '0.5rem', fontWeight: 600 }}>
                    [2] STREAM PROCESSING LAYER
                  </div>
                  <div style={{ color: '#666666', marginBottom: '0.5rem' }}>
                    Component: <code className="code-text">Spark Structured Streaming</code>
                  </div>
                  <div style={{ color: '#333333', fontSize: '0.8rem', lineHeight: '1.6' }}>
                    Consumes from: <code className="code-text">weather-raw</code><br/>
                    Window: 5-minute sliding windows, 1-minute slide interval<br/>
                    Aggregations: mean, std, min, max per window<br/>
                    Published to: <code className="code-text">weather-features</code> (4 partitions)<br/>
                    Cluster: 1 Master + 4 Workers | Checkpointing: enabled
                  </div>
                </div>

                <div style={{ textAlign: 'center', color: '#666666', margin: '0.5rem 0', fontSize: '1.2rem' }}>
                  ↓
                </div>

                <div style={{ 
                  padding: '1rem', 
                  backgroundColor: '#f8f9fa', 
                  borderLeft: '3px solid #ffc107',
                  marginBottom: '1rem',
                  borderRadius: '4px'
                }}>
                  <div style={{ color: '#ffc107', marginBottom: '0.5rem', fontWeight: 600 }}>
                    [3] ML INFERENCE LAYER
                  </div>
                  <div style={{ color: '#666666', marginBottom: '0.5rem' }}>
                    Component: <code className="code-text">Ray Distributed Actors</code>
                  </div>
                  <div style={{ color: '#333333', fontSize: '0.8rem', lineHeight: '1.6' }}>
                    Consumes from: <code className="code-text">weather-features</code><br/>
                    Tasks: Time series forecasting (24h horizon), Anomaly detection<br/>
                    Model: LSTM-based forecasting model<br/>
                    Published to: <code className="code-text">weather-predictions</code> (4 partitions)<br/>
                    Cluster: 1 Head + 4 Workers | Parallel inference execution
                  </div>
                </div>

                <div style={{ textAlign: 'center', color: '#666666', margin: '0.5rem 0', fontSize: '1.2rem' }}>
                  ↓
                </div>

                <div style={{ 
                  padding: '1rem', 
                  backgroundColor: '#f8f9fa', 
                  borderLeft: '3px solid #dc3545',
                  borderRadius: '4px'
                }}>
                  <div style={{ color: '#dc3545', marginBottom: '0.5rem', fontWeight: 600 }}>
                    [4] SERVING LAYER
                  </div>
                  <div style={{ color: '#666666', marginBottom: '0.5rem' }}>
                    Component: <code className="code-text">REST API</code>
                  </div>
                  <div style={{ color: '#333333', fontSize: '0.8rem', lineHeight: '1.6' }}>
                    Consumes from: <code className="code-text">weather-predictions</code><br/>
                    Endpoints: <code className="code-text">/health</code>, <code className="code-text">/predictions/latest</code>, <code className="code-text">/predictions</code><br/>
                    Protocol: HTTP/REST | Format: JSON
                  </div>
                </div>
              </div>
            </Card.Body>
          </Card>
        </Col>
      </Row>

      <Row className="mb-3">
        <Col md={6}>
          <Card className="bg-dark text-light">
            <Card.Header>
              <div className="section-title">System Components</div>
            </Card.Header>
            <Card.Body>
              <Table className="tech-table" hover>
                <thead>
                  <tr>
                    <th>Component</th>
                    <th>Count</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td><code className="code-text">Kafka Broker</code></td>
                    <td>1</td>
                  </tr>
                  <tr>
                    <td><code className="code-text">Spark Master</code></td>
                    <td>1</td>
                  </tr>
                  <tr>
                    <td><code className="code-text">Spark Workers</code></td>
                    <td>4</td>
                  </tr>
                  <tr>
                    <td><code className="code-text">Ray Head</code></td>
                    <td>1</td>
                  </tr>
                  <tr>
                    <td><code className="code-text">Ray Workers</code></td>
                    <td>4</td>
                  </tr>
                  <tr>
                    <td><code className="code-text">API Service</code></td>
                    <td>1</td>
                  </tr>
                </tbody>
              </Table>
            </Card.Body>
          </Card>
        </Col>
        <Col md={6}>
          <Card className="bg-dark text-light">
            <Card.Header>
              <div className="section-title">Resource Allocation</div>
            </Card.Header>
            <Card.Body>
              <Table className="tech-table" hover>
                <thead>
                  <tr>
                    <th>Resource</th>
                    <th>Value</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Total Containers</td>
                    <td><code className="code-text">14</code></td>
                  </tr>
                  <tr>
                    <td>Total CPU Cores</td>
                    <td><code className="code-text">13.5</code></td>
                  </tr>
                  <tr>
                    <td>Total RAM</td>
                    <td><code className="code-text">35 GB</code></td>
                  </tr>
                  <tr>
                    <td>Kafka Topics</td>
                    <td><code className="code-text">3</code></td>
                  </tr>
                  <tr>
                    <td>Partitions per Topic</td>
                    <td><code className="code-text">4</code></td>
                  </tr>
                  <tr>
                    <td>Network</td>
                    <td><code className="code-text">weather-network</code></td>
                  </tr>
                </tbody>
              </Table>
            </Card.Body>
          </Card>
        </Col>
      </Row>

      <Row>
        <Col md={12}>
          <Card className="bg-dark text-light">
            <Card.Header>
              <div className="section-title">Service Endpoints</div>
            </Card.Header>
            <Card.Body>
              <Table className="tech-table" hover>
                <thead>
                  <tr>
                    <th>Service</th>
                    <th>Endpoint</th>
                    <th>Purpose</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td><code className="code-text">Spark Master UI</code></td>
                    <td><code className="code-text">http://localhost:8080</code></td>
                    <td style={{ color: '#666666' }}>Cluster status and job monitoring</td>
                  </tr>
                  <tr>
                    <td><code className="code-text">Ray Dashboard</code></td>
                    <td><code className="code-text">http://localhost:8265</code></td>
                    <td style={{ color: '#666666' }}>Actor and task monitoring</td>
                  </tr>
                  <tr>
                    <td><code className="code-text">API Service</code></td>
                    <td><code className="code-text">http://localhost:5000</code></td>
                    <td style={{ color: '#666666' }}>REST API for predictions</td>
                  </tr>
                  <tr>
                    <td><code className="code-text">Kafka Broker</code></td>
                    <td><code className="code-text">localhost:9092</code></td>
                    <td style={{ color: '#666666' }}>Internal message broker</td>
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

export default Architecture
