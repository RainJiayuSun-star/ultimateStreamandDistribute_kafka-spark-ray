import { Card, Row, Col } from 'react-bootstrap'
import { WeatherPrediction, AllStationsResponse } from '../services/api'

interface SystemMetricsProps {
  predictions: WeatherPrediction[]
  allStationsData: AllStationsResponse | null
  lastUpdate: Date | null
}

function SystemMetrics({ predictions, allStationsData, lastUpdate }: SystemMetricsProps) {
  // Count stations from all sources (raw, features, predictions)
  const stationsFromPredictions = new Set(predictions.map(p => p.station_id))
  const stationsFromAllData = allStationsData ? new Set(Object.keys(allStationsData.stations)) : new Set()
  
  // Combine both sets to get total unique stations
  const allStations = new Set([...stationsFromPredictions, ...stationsFromAllData])
  const totalStations = allStations.size
  
  const totalPredictions = predictions.length
  const anomalyCount = predictions.filter(p => p.anomaly?.is_anomaly).length

  return (
    <Card className="bg-dark text-light mb-3 fade-in">
      <Card.Header>
        <div className="section-title">System Metrics</div>
      </Card.Header>
      <Card.Body>
        <Row>
          <Col md={3}>
            <div className="metric-label">Active Stations</div>
            <div className="metric-value">{totalStations}</div>
          </Col>
          <Col md={3}>
            <div className="metric-label">Predictions</div>
            <div className="metric-value">{totalPredictions}</div>
          </Col>
          <Col md={3}>
            <div className="metric-label">Anomalies Detected</div>
            <div className="metric-value" style={{ color: anomalyCount > 0 ? '#dc3545' : '#28a745' }}>
              {anomalyCount}
            </div>
          </Col>
          <Col md={3}>
            <div className="metric-label">Last Update</div>
            <div className="metric-value" style={{ fontSize: '1rem' }}>
              {lastUpdate 
                ? new Date(lastUpdate).toLocaleTimeString('en-US', { 
                    hour12: false,
                    hour: '2-digit',
                    minute: '2-digit',
                    second: '2-digit'
                  })
                : 'N/A'}
            </div>
          </Col>
        </Row>
      </Card.Body>
    </Card>
  )
}

export default SystemMetrics
