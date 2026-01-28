import { useEffect, useRef } from 'react'
import { Card, Badge, Row, Col } from 'react-bootstrap'

interface StationData {
  station_id: string
  station_name: string
  raw: Array<{
    partition: number
    offset: number
    timestamp: string
    data: any
  }>
  features: Array<{
    partition: number
    offset: number
    timestamp: string
    data: any
  }>
  predictions: Array<{
    partition: number
    offset: number
    timestamp: string
    data: any
  }>
}

interface StationDataListProps {
  stations: { [stationId: string]: StationData }
  loading: boolean
}

function StationDataList({ stations, loading }: StationDataListProps) {
  const scrollRef = useRef<HTMLDivElement>(null)
  const prevDataRef = useRef<string>('')

  useEffect(() => {
    // Auto-scroll to top when new data arrives
    const currentData = JSON.stringify(Object.keys(stations).sort())
    if (scrollRef.current && currentData !== prevDataRef.current && currentData !== '[]') {
      // Scroll to top when new data is detected
      scrollRef.current.scrollTop = 0
    }
    prevDataRef.current = currentData
  }, [stations])

  const stationList = Object.values(stations)

  return (
    <Card className="bg-dark text-light fade-in">
      <Card.Header>
        <div className="section-title">All Stations Data</div>
        <small style={{ color: '#666666', fontSize: '0.75rem' }}>
          Real-time data from all Kafka topics
        </small>
      </Card.Header>
      <Card.Body>
        <div
          ref={scrollRef}
          style={{
            maxHeight: '600px',
            overflowY: 'auto',
            padding: '0.5rem',
            transition: 'opacity 0.3s ease'
          }}
        >
          {loading && stationList.length === 0 ? (
            <div style={{ color: '#666666', textAlign: 'center', padding: '2rem' }}>
              Loading station data...
            </div>
          ) : stationList.length === 0 ? (
            <div style={{ color: '#666666', textAlign: 'center', padding: '2rem' }}>
              No station data available
            </div>
          ) : (
            stationList.map((station) => (
              <Card
                key={station.station_id}
                className="mb-3 fade-in"
                style={{
                  backgroundColor: '#ffffff',
                  border: '1px solid #e0e0e0',
                  transition: 'transform 0.2s ease, box-shadow 0.2s ease'
                }}
              >
                <Card.Header style={{ backgroundColor: '#f8f9fa', borderBottom: '1px solid #e0e0e0' }}>
                  <h5 style={{ color: '#333333', margin: 0 }}>
                    <code style={{ fontFamily: 'Courier New, monospace', fontSize: '0.875rem', color: '#28a745', backgroundColor: '#f5f5f5', padding: '0.2rem 0.4rem', borderRadius: '3px' }}>
                      {station.station_id}
                    </code>
                    {station.station_name && (
                      <span style={{ color: '#666666', marginLeft: '0.5rem', fontWeight: 'normal', fontSize: '0.9rem' }}>
                        - {station.station_name}
                      </span>
                    )}
                  </h5>
                </Card.Header>
                <Card.Body>
                  <Row>
                    {/* Raw Data Card */}
                    {station.raw.length > 0 && (
                      <Col md={4} className="mb-3">
                        <Card style={{ 
                          backgroundColor: '#f8f9fa', 
                          border: '1px solid #e0e0e0',
                          height: '100%',
                          display: 'flex',
                          flexDirection: 'column'
                        }}>
                          <Card.Header style={{ 
                            backgroundColor: '#ffffff', 
                            borderBottom: '1px solid #e0e0e0',
                            padding: '0.5rem 0.75rem'
                          }}>
                            <Badge bg="primary" style={{ fontSize: '0.75rem' }}>
                              RAW DATA ({station.raw.length})
                            </Badge>
                          </Card.Header>
                          <Card.Body style={{ 
                            padding: '0.5rem',
                            flex: 1,
                            overflow: 'hidden',
                            display: 'flex',
                            flexDirection: 'column'
                          }}>
                            <div style={{
                              maxHeight: '300px',
                              overflowY: 'auto',
                              flex: 1
                            }}>
                              {station.raw.map((item, idx) => (
                                <div
                                  key={idx}
                                  className="fade-in"
                                  style={{
                                    padding: '0.5rem',
                                    marginBottom: '0.5rem',
                                    backgroundColor: '#ffffff',
                                    borderRadius: '3px',
                                    border: '1px solid #e0e0e0',
                                    fontSize: '0.75rem',
                                    fontFamily: 'monospace'
                                  }}
                                >
                                  <div style={{ color: '#666666', marginBottom: '0.25rem', fontSize: '0.7rem' }}>
                                    P{item.partition} | {new Date(item.timestamp).toLocaleString()}
                                  </div>
                                  <div>
                                    {item.data.temperature !== undefined && (
                                      <div style={{ marginBottom: '0.25rem' }}>
                                        <span style={{ color: '#666666' }}>Temp:</span>{' '}
                                        <strong>{item.data.temperature?.toFixed(1)}°F</strong>
                                      </div>
                                    )}
                                    {item.data.humidity !== undefined && (
                                      <div style={{ marginBottom: '0.25rem' }}>
                                        <span style={{ color: '#666666' }}>Humidity:</span>{' '}
                                        <strong>{item.data.humidity?.toFixed(1)}%</strong>
                                      </div>
                                    )}
                                    {item.data.sea_level_pressure !== undefined && (
                                      <div style={{ marginBottom: '0.25rem' }}>
                                        <span style={{ color: '#666666' }}>Pressure:</span>{' '}
                                        <strong>{item.data.sea_level_pressure?.toFixed(1)} hPa</strong>
                                      </div>
                                    )}
                                    {item.data.wind_speed !== undefined && (
                                      <div>
                                        <span style={{ color: '#666666' }}>Wind:</span>{' '}
                                        <strong>{item.data.wind_speed?.toFixed(1)} m/s</strong>
                                      </div>
                                    )}
                                  </div>
                                </div>
                              ))}
                            </div>
                          </Card.Body>
                        </Card>
                      </Col>
                    )}

                    {/* Features Data Card */}
                    {station.features.length > 0 && (
                      <Col md={4} className="mb-3">
                        <Card style={{ 
                          backgroundColor: '#f8f9fa', 
                          border: '1px solid #e0e0e0',
                          height: '100%',
                          display: 'flex',
                          flexDirection: 'column'
                        }}>
                          <Card.Header style={{ 
                            backgroundColor: '#ffffff', 
                            borderBottom: '1px solid #e0e0e0',
                            padding: '0.5rem 0.75rem'
                          }}>
                            <Badge bg="success" style={{ fontSize: '0.75rem' }}>
                              FEATURES ({station.features.length})
                            </Badge>
                          </Card.Header>
                          <Card.Body style={{ 
                            padding: '0.5rem',
                            flex: 1,
                            overflow: 'hidden',
                            display: 'flex',
                            flexDirection: 'column'
                          }}>
                            <div style={{
                              maxHeight: '300px',
                              overflowY: 'auto',
                              flex: 1
                            }}>
                              {station.features.map((item, idx) => (
                                <div
                                  key={idx}
                                  className="fade-in"
                                  style={{
                                    padding: '0.5rem',
                                    marginBottom: '0.5rem',
                                    backgroundColor: '#ffffff',
                                    borderRadius: '3px',
                                    border: '1px solid #e0e0e0',
                                    fontSize: '0.75rem',
                                    fontFamily: 'monospace'
                                  }}
                                >
                                  <div style={{ color: '#666666', marginBottom: '0.25rem', fontSize: '0.7rem' }}>
                                    P{item.partition} | {new Date(item.timestamp).toLocaleString()}
                                  </div>
                                  {item.data.window_start && (
                                    <div style={{ color: '#666666', fontSize: '0.65rem', marginBottom: '0.25rem' }}>
                                      Window: {new Date(item.data.window_start).toLocaleTimeString()} - {item.data.window_end ? new Date(item.data.window_end).toLocaleTimeString() : ''}
                                    </div>
                                  )}
                                  <div>
                                    {item.data.temperature_mean !== undefined && (
                                      <div style={{ marginBottom: '0.25rem' }}>
                                        <span style={{ color: '#666666' }}>T_avg:</span>{' '}
                                        <strong>{item.data.temperature_mean?.toFixed(1)}°F</strong>
                                      </div>
                                    )}
                                    {item.data.humidity_mean !== undefined && (
                                      <div style={{ marginBottom: '0.25rem' }}>
                                        <span style={{ color: '#666666' }}>H_avg:</span>{' '}
                                        <strong>{item.data.humidity_mean?.toFixed(1)}%</strong>
                                      </div>
                                    )}
                                    {item.data.pressure_mean !== undefined && (
                                      <div style={{ marginBottom: '0.25rem' }}>
                                        <span style={{ color: '#666666' }}>P_avg:</span>{' '}
                                        <strong>{item.data.pressure_mean?.toFixed(1)} hPa</strong>
                                      </div>
                                    )}
                                    {item.data.wind_speed_mean !== undefined && (
                                      <div>
                                        <span style={{ color: '#666666' }}>W_avg:</span>{' '}
                                        <strong>{item.data.wind_speed_mean?.toFixed(1)} m/s</strong>
                                      </div>
                                    )}
                                  </div>
                                </div>
                              ))}
                            </div>
                          </Card.Body>
                        </Card>
                      </Col>
                    )}

                    {/* Predictions Data Card */}
                    {station.predictions.length > 0 && (
                      <Col md={4} className="mb-3">
                        <Card style={{ 
                          backgroundColor: '#f8f9fa', 
                          border: '1px solid #e0e0e0',
                          height: '100%',
                          display: 'flex',
                          flexDirection: 'column'
                        }}>
                          <Card.Header style={{ 
                            backgroundColor: '#ffffff', 
                            borderBottom: '1px solid #e0e0e0',
                            padding: '0.5rem 0.75rem'
                          }}>
                            <Badge bg="warning" style={{ fontSize: '0.75rem' }}>
                              PREDICTIONS ({station.predictions.length})
                            </Badge>
                          </Card.Header>
                          <Card.Body style={{ 
                            padding: '0.5rem',
                            flex: 1,
                            overflow: 'hidden',
                            display: 'flex',
                            flexDirection: 'column'
                          }}>
                            <div style={{
                              maxHeight: '300px',
                              overflowY: 'auto',
                              flex: 1
                            }}>
                              {station.predictions.map((item, idx) => {
                                const predictionData = item.data
                                const forecast = predictionData.forecast || {}
                                const temperaturePredictions = forecast.temperature_predictions || predictionData.predictions?.temperature || []
                                
                                return (
                                  <div
                                    key={idx}
                                    className="fade-in"
                                    style={{
                                      padding: '0.75rem',
                                      marginBottom: '0.5rem',
                                      backgroundColor: '#ffffff',
                                      borderRadius: '3px',
                                      border: '1px solid #e0e0e0',
                                      fontSize: '0.75rem',
                                      fontFamily: 'monospace'
                                    }}
                                  >
                                    <div style={{ color: '#666666', marginBottom: '0.5rem', fontSize: '0.7rem' }}>
                                      P{item.partition} | {new Date(item.timestamp).toLocaleString()}
                                    </div>
                                    
                                    {/* Current Conditions */}
                                    {predictionData.current_conditions && (
                                      <div style={{ marginBottom: '0.75rem', paddingBottom: '0.5rem', borderBottom: '1px solid #e0e0e0' }}>
                                        <div style={{ color: '#666666', fontSize: '0.7rem', marginBottom: '0.25rem', fontWeight: 600 }}>
                                          Current Conditions:
                                        </div>
                                        {predictionData.current_conditions.temperature_mean !== undefined && (
                                          <div style={{ fontSize: '0.7rem', marginBottom: '0.15rem' }}>
                                            <span style={{ color: '#666666' }}>T:</span>{' '}
                                            <strong>{predictionData.current_conditions.temperature_mean?.toFixed(1)}°F</strong>
                                          </div>
                                        )}
                                        {predictionData.current_conditions.humidity_mean !== undefined && (
                                          <div style={{ fontSize: '0.7rem', marginBottom: '0.15rem' }}>
                                            <span style={{ color: '#666666' }}>H:</span>{' '}
                                            <strong>{predictionData.current_conditions.humidity_mean?.toFixed(1)}%</strong>
                                          </div>
                                        )}
                                        {predictionData.current_conditions.pressure_mean !== undefined && (
                                          <div style={{ fontSize: '0.7rem' }}>
                                            <span style={{ color: '#666666' }}>P:</span>{' '}
                                            <strong>{predictionData.current_conditions.pressure_mean?.toFixed(1)} hPa</strong>
                                          </div>
                                        )}
                                      </div>
                                    )}

                                    {/* 24-Hour Forecast */}
                                    {Array.isArray(temperaturePredictions) && temperaturePredictions.length > 0 && (
                                      <div>
                                        <div style={{ color: '#0066cc', fontSize: '0.7rem', marginBottom: '0.5rem', fontWeight: 600 }}>
                                          24-Hour Forecast ({temperaturePredictions.length}h):
                                        </div>
                                        <div style={{
                                          maxHeight: '200px',
                                          overflowY: 'auto',
                                          padding: '0.5rem',
                                          backgroundColor: '#f8f9fa',
                                          borderRadius: '3px',
                                          border: '1px solid #e0e0e0',
                                          marginBottom: '0.5rem'
                                        }}>
                                          {temperaturePredictions.map((temp: number, hourIdx: number) => (
                                            <div
                                              key={hourIdx}
                                              style={{
                                                fontSize: '0.7rem',
                                                padding: '0.2rem 0',
                                                borderBottom: hourIdx < temperaturePredictions.length - 1 ? '1px solid #e0e0e0' : 'none'
                                              }}
                                            >
                                              <span style={{ color: '#666666', marginRight: '0.5rem' }}>
                                                +{hourIdx + 1}h:
                                              </span>
                                              <strong style={{ color: '#0066cc' }}>
                                                {temp?.toFixed(1)}°F
                                              </strong>
                                            </div>
                                          ))}
                                        </div>
                                        <div style={{ fontSize: '0.7rem' }}>
                                          <strong>
                                            Now: {temperaturePredictions[0]?.toFixed(1)}°F
                                            {temperaturePredictions.length > 1 && (
                                              <span style={{ marginLeft: '0.5rem', color: '#666666' }}>
                                                → 24h: {temperaturePredictions[temperaturePredictions.length - 1]?.toFixed(1)}°F
                                              </span>
                                            )}
                                          </strong>
                                        </div>
                                      </div>
                                    )}

                                    {/* Horizon Hours */}
                                    {(forecast.horizon_hours || predictionData.horizon_hours) && (
                                      <div style={{ color: '#666666', fontSize: '0.65rem', marginTop: '0.5rem' }}>
                                        Horizon: {forecast.horizon_hours || predictionData.horizon_hours}h
                                      </div>
                                    )}

                                    {/* Anomaly */}
                                    {predictionData.anomaly?.is_anomaly && (
                                      <div style={{ marginTop: '0.5rem' }}>
                                        <Badge bg="danger" style={{ fontSize: '0.65rem' }}>ANOMALY DETECTED</Badge>
                                      </div>
                                    )}
                                  </div>
                                )
                              })}
                            </div>
                          </Card.Body>
                        </Card>
                      </Col>
                    )}
                  </Row>
                </Card.Body>
              </Card>
            ))
          )}
        </div>
      </Card.Body>
    </Card>
  )
}

export default StationDataList
