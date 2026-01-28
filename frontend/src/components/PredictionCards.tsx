import { Row, Col, Card, Badge, Spinner } from 'react-bootstrap'
import { WeatherPrediction } from '../services/api'

interface PredictionCardsProps {
  predictions: WeatherPrediction[]
  loading: boolean
}

function PredictionCards({ predictions, loading }: PredictionCardsProps) {
  if (loading && predictions.length === 0) {
    return (
      <Card className="bg-dark text-light">
        <Card.Header>
          <div className="section-title">Prediction Results</div>
        </Card.Header>
        <Card.Body>
          <div className="text-center" style={{ padding: '2rem' }}>
            <Spinner animation="border" variant="light" />
            <p style={{ color: '#888', marginTop: '1rem', fontSize: '0.875rem' }}>
              Loading predictions from Kafka topic...
            </p>
          </div>
        </Card.Body>
      </Card>
    )
  }

  if (predictions.length === 0) {
    return (
      <Card className="bg-dark text-light">
        <Card.Header>
          <div className="section-title">Prediction Results</div>
        </Card.Header>
        <Card.Body>
          <div style={{ 
            padding: '2rem', 
            textAlign: 'center',
            color: '#666666',
            fontFamily: 'monospace',
            fontSize: '0.875rem'
          }}>
            <div style={{ marginBottom: '1rem' }}>
              <code className="code-text">NO_PREDICTIONS_AVAILABLE</code>
            </div>
            <div style={{ fontSize: '0.75rem', lineHeight: '1.6' }}>
              Waiting for data from pipeline:<br/>
              <code className="code-text">weather-raw</code> → 
              <code className="code-text">weather-features</code> → 
              <code className="code-text">weather-predictions</code>
            </div>
          </div>
        </Card.Body>
      </Card>
    )
  }

  return (
    <Card className="bg-dark text-light fade-in">
      <Card.Header>
        <div className="section-title">Prediction Results</div>
      </Card.Header>
      <Card.Body>
        <Row>
          {predictions.map((prediction, index) => (
            <Col key={index} md={6} lg={4} className="mb-3">
              <Card 
                className={`bg-dark text-light fade-in ${prediction.anomaly?.is_anomaly ? 'anomaly-card' : 'prediction-card'}`}
                style={{ transition: 'transform 0.2s ease, opacity 0.3s ease' }}
              >
                <Card.Header className="d-flex justify-content-between align-items-center">
                  <code className="code-text" style={{ fontSize: '0.875rem' }}>
                    {prediction.station_id}
                  </code>
                  {prediction.anomaly?.is_anomaly && (
                    <Badge className="status-error">ANOMALY</Badge>
                  )}
                </Card.Header>
                <Card.Body>
                  <div className="mb-3" style={{ fontSize: '0.75rem', color: '#666666' }}>
                    <div>Station: <span style={{ color: '#333333' }}>{prediction.station_name || prediction.station_id}</span></div>
                    <div>Timestamp: <span className="code-text">{new Date(prediction.timestamp).toISOString()}</span></div>
                    {prediction.partition !== undefined && (
                      <div>Partition: <span className="code-text">{prediction.partition}</span></div>
                    )}
                  </div>
                  
                  {prediction.predictions && (
                    <div style={{ fontFamily: 'monospace', fontSize: '0.875rem' }}>
                      {prediction.predictions.temperature && (
                        <div className="mb-2">
                          <span className="metric-label">Temperature</span>
                          <div>
                            <span className="metric-value" style={{ fontSize: '1.25rem' }}>
                              {prediction.predictions.temperature[0]?.toFixed(1)}
                            </span>
                            <span className="metric-unit">°F</span>
                            {prediction.predictions.temperature.length > 1 && (
                              <span style={{ color: '#888', marginLeft: '0.5rem', fontSize: '0.75rem' }}>
                                (24h: {prediction.predictions.temperature[prediction.predictions.temperature.length - 1]?.toFixed(1)}°F)
                              </span>
                            )}
                          </div>
                        </div>
                      )}
                      
                      {prediction.predictions.humidity && (
                        <div className="mb-2">
                          <span className="metric-label">Humidity</span>
                          <div>
                            <span className="metric-value" style={{ fontSize: '1.25rem' }}>
                              {prediction.predictions.humidity[0]?.toFixed(1)}
                            </span>
                            <span className="metric-unit">%</span>
                          </div>
                        </div>
                      )}
                      
                      {prediction.predictions.pressure && (
                        <div className="mb-2">
                          <span className="metric-label">Pressure</span>
                          <div>
                            <span className="metric-value" style={{ fontSize: '1.25rem' }}>
                              {prediction.predictions.pressure[0]?.toFixed(1)}
                            </span>
                            <span className="metric-unit">hPa</span>
                          </div>
                        </div>
                      )}
                      
                      {prediction.predictions.wind_speed && (
                        <div className="mb-2">
                          <span className="metric-label">Wind Speed</span>
                          <div>
                            <span className="metric-value" style={{ fontSize: '1.25rem' }}>
                              {prediction.predictions.wind_speed[0]?.toFixed(1)}
                            </span>
                            <span className="metric-unit">m/s</span>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                  
                  <div className="mt-3" style={{ fontSize: '0.75rem', color: '#666666', borderTop: '1px solid #e0e0e0', paddingTop: '0.5rem' }}>
                    {prediction.confidence && (
                      <div>Confidence: <span className="code-text">{(prediction.confidence * 100).toFixed(1)}%</span></div>
                    )}
                    {prediction.anomaly && (
                      <div>Anomaly Score: <span className="code-text">{prediction.anomaly.score?.toFixed(3) || 'N/A'}</span></div>
                    )}
                  </div>
                </Card.Body>
              </Card>
            </Col>
          ))}
        </Row>
      </Card.Body>
    </Card>
  )
}

export default PredictionCards
