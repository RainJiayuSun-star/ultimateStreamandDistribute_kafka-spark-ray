import { useRef, useEffect } from 'react'
import { Card, Row, Col, Badge } from 'react-bootstrap'

interface MessageData {
  offset: number
  timestamp: string
  data: any
}

interface PartitionData {
  [partition: number]: MessageData[]
}

interface KafkaTopicSectionProps {
  title: string
  topicName: string
  partitionData: PartitionData
  loading: boolean
}

function KafkaTopicSection({ title, topicName, partitionData, loading }: KafkaTopicSectionProps) {
  const partitions = Object.keys(partitionData).map(Number).sort()
  const scrollRefs = useRef<{ [key: number]: HTMLDivElement | null }>({})

  useEffect(() => {
    // Auto-scroll each partition to bottom (newest messages) when new data arrives
    const timeoutId = setTimeout(() => {
      partitions.forEach((partition) => {
        const scrollRef = scrollRefs.current[partition]
        if (scrollRef) {
          // Scroll to bottom to show newest messages
          scrollRef.scrollTop = scrollRef.scrollHeight
        }
      })
    }, 100) // Small delay to ensure DOM is updated
    
    return () => clearTimeout(timeoutId)
  }, [partitionData, partitions])

  return (
    <Card className="bg-dark text-light mb-3" style={{ transition: 'opacity 0.3s ease' }}>
      <Card.Header>
        <div className="section-title">{title}</div>
        <small style={{ color: '#666666', fontSize: '0.75rem' }}>
          Topic: <code className="code-text">{topicName}</code>
        </small>
      </Card.Header>
      <Card.Body style={{ transition: 'opacity 0.3s ease' }}>
        {loading && Object.keys(partitionData).length === 0 ? (
          <div style={{ color: '#666666', textAlign: 'center', padding: '1rem' }}>
            Loading...
          </div>
        ) : partitions.length === 0 ? (
          <div style={{ color: '#666666', textAlign: 'center', padding: '1rem' }}>
            No data available
          </div>
        ) : (
          <Row>
            {partitions.map((partition) => {
              // Handle both array format (new) and single object format (old/fallback)
              const partitionDataValue = partitionData[partition]
              const messages = Array.isArray(partitionDataValue) 
                ? partitionDataValue 
                : partitionDataValue 
                  ? [partitionDataValue] 
                  : []
              return (
                <Col key={partition} md={3} className="mb-3">
                  <div style={{
                    padding: '0.75rem',
                    backgroundColor: '#ffffff',
                    borderRadius: '4px',
                    border: '1px solid #e0e0e0',
                    height: '100%',
                    display: 'flex',
                    flexDirection: 'column'
                  }}>
                    <div className="mb-2">
                      <Badge bg="secondary" style={{ fontSize: '0.75rem' }}>
                        Partition {partition}
                      </Badge>
                      <span style={{ color: '#666666', fontSize: '0.75rem', marginLeft: '0.5rem' }}>
                        ({messages.length} messages)
                      </span>
                    </div>
                    <div
                      ref={(el) => { scrollRefs.current[partition] = el }}
                      style={{
                        maxHeight: '400px',
                        overflowY: 'auto',
                        overflowX: 'hidden',
                        padding: '0.25rem'
                      }}
                    >
                      {messages.length === 0 ? (
                        <div style={{ color: '#666666', fontSize: '0.75rem', textAlign: 'center', padding: '1rem' }}>
                          No messages
                        </div>
                      ) : (
                        messages.map((message, idx) => {
                          // Normalize message format - handle both new format (with .data) and old format (direct object)
                          const messageData = message.data || message
                          const messageTimestamp = message.timestamp || messageData.timestamp || new Date().toISOString()
                          const messageOffset = message.offset !== undefined ? message.offset : idx
                          
                          return (
                            <div
                              key={`${messageOffset}-${idx}`}
                              className="fade-in"
                              style={{
                                padding: '0.5rem',
                                marginBottom: '0.5rem',
                                backgroundColor: '#f8f9fa',
                                borderRadius: '3px',
                                border: '1px solid #e0e0e0',
                                fontSize: '0.75rem',
                                fontFamily: 'monospace',
                                transition: 'background-color 0.2s ease, transform 0.2s ease'
                              }}
                            >
                            <div style={{ color: '#666666', marginBottom: '0.25rem', fontSize: '0.7rem' }}>
                              {new Date(messageTimestamp).toLocaleString()}
                            </div>
                            {messageData.station_id && (
                              <div className="mb-1">
                                <span style={{ color: '#666666' }}>Station:</span>{' '}
                                <code className="code-text" style={{ fontSize: '0.7rem' }}>
                                  {messageData.station_id}
                                </code>
                              </div>
                            )}
                            {messageData.window_start && (
                              <div style={{ color: '#666666', fontSize: '0.65rem', marginBottom: '0.25rem' }}>
                                Window: {new Date(messageData.window_start).toLocaleTimeString()} - {messageData.window_end ? new Date(messageData.window_end).toLocaleTimeString() : ''}
                              </div>
                            )}
                              {messageData.temperature !== undefined && (
                                <div className="mb-1">
                                  <span style={{ color: '#666666' }}>Temp:</span>{' '}
                                  <strong>{messageData.temperature?.toFixed(1)}°F</strong>
                                </div>
                              )}
                              {messageData.humidity !== undefined && (
                                <div className="mb-1">
                                  <span style={{ color: '#666666' }}>Humidity:</span>{' '}
                                  <strong>{messageData.humidity?.toFixed(1)}%</strong>
                                </div>
                              )}
                              {messageData.pressure !== undefined && (
                                <div className="mb-1">
                                  <span style={{ color: '#666666' }}>Pressure:</span>{' '}
                                  <strong>{messageData.pressure?.toFixed(1)} hPa</strong>
                                </div>
                              )}
                              {messageData.sea_level_pressure !== undefined && (
                                <div className="mb-1">
                                  <span style={{ color: '#666666' }}>Pressure:</span>{' '}
                                  <strong>{messageData.sea_level_pressure?.toFixed(1)} hPa</strong>
                                </div>
                              )}
                              {messageData.wind_speed !== undefined && (
                                <div className="mb-1">
                                  <span style={{ color: '#666666' }}>Wind:</span>{' '}
                                  <strong>{messageData.wind_speed?.toFixed(1)} m/s</strong>
                                </div>
                              )}
                              {messageData.wind_speed_mean !== undefined && (
                                <div className="mb-1">
                                  <span style={{ color: '#666666' }}>Wind Avg:</span>{' '}
                                  <strong>{messageData.wind_speed_mean?.toFixed(1)} m/s</strong>
                                </div>
                              )}
                              {messageData.current_conditions?.wind_speed_mean !== undefined && (
                                <div className="mb-1">
                                  <span style={{ color: '#666666' }}>Wind Avg:</span>{' '}
                                  <strong>{messageData.current_conditions.wind_speed_mean?.toFixed(1)} m/s</strong>
                                </div>
                              )}
                              {messageData.temperature_mean !== undefined && (
                                <div className="mb-1">
                                  <span style={{ color: '#666666' }}>T_avg:</span>{' '}
                                  <strong>{messageData.temperature_mean?.toFixed(1)}°F</strong>
                                </div>
                              )}
                              {messageData.humidity_mean !== undefined && (
                                <div className="mb-1">
                                  <span style={{ color: '#666666' }}>H_avg:</span>{' '}
                                  <strong>{messageData.humidity_mean?.toFixed(1)}%</strong>
                                </div>
                              )}
                              {/* Current Conditions (from predictions) */}
                              {messageData.current_conditions && (
                                <>
                                  {messageData.current_conditions.temperature_mean !== undefined && (
                                    <div className="mb-1">
                                      <span style={{ color: '#666666' }}>Current T:</span>{' '}
                                      <strong>{messageData.current_conditions.temperature_mean?.toFixed(1)}°F</strong>
                                    </div>
                                  )}
                                  {messageData.current_conditions.humidity_mean !== undefined && (
                                    <div className="mb-1">
                                      <span style={{ color: '#666666' }}>Current H:</span>{' '}
                                      <strong>{messageData.current_conditions.humidity_mean?.toFixed(1)}%</strong>
                                    </div>
                                  )}
                                  {messageData.current_conditions.pressure_mean !== undefined && (
                                    <div className="mb-1">
                                      <span style={{ color: '#666666' }}>Current P:</span>{' '}
                                      <strong>{messageData.current_conditions.pressure_mean?.toFixed(1)} hPa</strong>
                                    </div>
                                  )}
                                </>
                              )}
                              {/* Forecast predictions */}
                              {messageData.forecast && (
                                <>
                                  {messageData.forecast.temperature_predictions && Array.isArray(messageData.forecast.temperature_predictions) && (
                                    <div className="mb-2" style={{ color: '#0066cc' }}>
                                      <div style={{ color: '#666666', fontSize: '0.7rem', marginBottom: '0.5rem', fontWeight: 600 }}>
                                        24-Hour Forecast ({messageData.forecast.temperature_predictions.length} hours):
                                      </div>
                                      <div style={{ 
                                        maxHeight: '150px', 
                                        overflowY: 'auto', 
                                        padding: '0.25rem',
                                        backgroundColor: '#ffffff',
                                        borderRadius: '3px',
                                        border: '1px solid #e0e0e0'
                                      }}>
                                        {messageData.forecast.temperature_predictions.map((temp: number, hourIdx: number) => (
                                          <div 
                                            key={hourIdx}
                                            style={{ 
                                              fontSize: '0.7rem',
                                              padding: '0.2rem 0',
                                              borderBottom: hourIdx < messageData.forecast.temperature_predictions.length - 1 ? '1px solid #f0f0f0' : 'none'
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
                                      <div style={{ marginTop: '0.25rem' }}>
                                        <strong>
                                          Now: {messageData.forecast.temperature_predictions[0]?.toFixed(1)}°F
                                          {messageData.forecast.temperature_predictions.length > 1 && (
                                            <span style={{ fontSize: '0.7rem', marginLeft: '0.5rem' }}>
                                              → 24h: {messageData.forecast.temperature_predictions[messageData.forecast.temperature_predictions.length - 1]?.toFixed(1)}°F
                                            </span>
                                          )}
                                        </strong>
                                      </div>
                                    </div>
                                  )}
                                  {messageData.forecast.horizon_hours && (
                                    <div style={{ color: '#666666', fontSize: '0.7rem' }}>
                                      Horizon: {messageData.forecast.horizon_hours}h
                                    </div>
                                  )}
                                </>
                              )}
                              {/* Legacy predictions format */}
                              {messageData.predictions && (
                                <>
                                  {messageData.predictions.temperature && Array.isArray(messageData.predictions.temperature) && (
                                    <div className="mb-2" style={{ color: '#0066cc' }}>
                                      <div style={{ color: '#666666', fontSize: '0.7rem', marginBottom: '0.5rem', fontWeight: 600 }}>
                                        24-Hour Forecast ({messageData.predictions.temperature.length} hours):
                                      </div>
                                      <div style={{ 
                                        maxHeight: '150px', 
                                        overflowY: 'auto', 
                                        padding: '0.25rem',
                                        backgroundColor: '#ffffff',
                                        borderRadius: '3px',
                                        border: '1px solid #e0e0e0'
                                      }}>
                                        {messageData.predictions.temperature.map((temp: number, hourIdx: number) => (
                                          <div 
                                            key={hourIdx}
                                            style={{ 
                                              fontSize: '0.7rem',
                                              padding: '0.2rem 0',
                                              borderBottom: hourIdx < messageData.predictions.temperature.length - 1 ? '1px solid #f0f0f0' : 'none'
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
                                      <div style={{ marginTop: '0.25rem' }}>
                                        <strong>
                                          Now: {messageData.predictions.temperature[0]?.toFixed(1)}°F
                                          {messageData.predictions.temperature.length > 1 && (
                                            <span style={{ fontSize: '0.7rem', marginLeft: '0.5rem' }}>
                                              → 24h: {messageData.predictions.temperature[messageData.predictions.temperature.length - 1]?.toFixed(1)}°F
                                            </span>
                                          )}
                                        </strong>
                                      </div>
                                    </div>
                                  )}
                                </>
                              )}
                              {messageData.anomaly?.is_anomaly && (
                                <div>
                                  <Badge bg="danger" style={{ fontSize: '0.65rem' }}>ANOMALY</Badge>
                                </div>
                              )}
                              {messageData.horizon_hours && (
                                <div style={{ color: '#666666', fontSize: '0.7rem', marginTop: '0.25rem' }}>
                                  Horizon: {messageData.horizon_hours}h
                                </div>
                              )}
                            </div>
                          )
                        })
                      )}
                    </div>
                  </div>
                </Col>
              )
            })}
          </Row>
        )}
      </Card.Body>
    </Card>
  )
}

export default KafkaTopicSection
