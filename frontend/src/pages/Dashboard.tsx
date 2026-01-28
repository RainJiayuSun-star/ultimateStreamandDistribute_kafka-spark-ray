import { useEffect, useState } from 'react'
import { Row, Col, Spinner, Alert } from 'react-bootstrap'
import SystemMetrics from '../components/SystemMetrics'
import KafkaTopicSection from '../components/KafkaTopicSection'
import StationDataList from '../components/StationDataList'
import SystemHealthAndPipeline from '../components/SystemHealthAndPipeline'
import api, { WeatherPrediction, TopicResponse, AllStationsResponse } from '../services/api'

function Dashboard() {
  const [predictions, setPredictions] = useState<WeatherPrediction[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null)
  
  // Kafka topic data
  const [weatherRaw, setWeatherRaw] = useState<TopicResponse | null>(null)
  const [weatherFeatures, setWeatherFeatures] = useState<TopicResponse | null>(null)
  const [weatherPredictionsTopic, setWeatherPredictionsTopic] = useState<TopicResponse | null>(null)
  const [allStationsData, setAllStationsData] = useState<AllStationsResponse | null>(null)
  const [topicsLoading, setTopicsLoading] = useState(true)

  useEffect(() => {
    const fetchPredictions = async () => {
      try {
        setLoading(true)
        const response = await api.getLatestPredictions()
        setPredictions(response.predictions || [])
        setLastUpdate(new Date())
        setError(null) // Clear any previous errors
      } catch (err: any) {
        // Only show error for actual connection issues, not 404s (handled in API service)
        if (err.code === 'ERR_NETWORK' || err.response?.status >= 500) {
          setError('Failed to connect to API. Make sure the API service is running on port 5000.')
        } else {
          setError(null)
          setPredictions([]) // Treat other errors as no data
        }
        console.error('Error fetching predictions:', err)
      } finally {
        setLoading(false)
      }
    }

    fetchPredictions()
    // Refresh every 30 seconds
    const interval = setInterval(fetchPredictions, 30000)

    return () => clearInterval(interval)
  }, [])

  // Fetch Kafka topic data with smooth updates
  useEffect(() => {
    let isMounted = true
    
    const fetchTopicData = async () => {
      try {
        // Don't show loading spinner on refresh, just update data smoothly
        const [raw, features, predictionsTopic, stations] = await Promise.all([
          api.getWeatherRaw(),
          api.getWeatherFeatures(),
          api.getWeatherPredictionsTopic(),
          api.getAllStationsData()
        ])
        
        if (isMounted) {
          // Update state smoothly without showing loading spinner
          setWeatherRaw(raw)
          setWeatherFeatures(features)
          setWeatherPredictionsTopic(predictionsTopic)
          setAllStationsData(stations)
          setTopicsLoading(false)
        }
      } catch (err) {
        console.error('Error fetching topic data:', err)
        if (isMounted) {
          setTopicsLoading(false)
        }
      }
    }

    // Initial load with loading state
    setTopicsLoading(true)
    fetchTopicData()
    
    // Refresh every 10 seconds for real-time updates (without loading spinner)
    const interval = setInterval(() => {
      fetchTopicData()
    }, 10000)

    return () => {
      isMounted = false
      clearInterval(interval)
    }
  }, [])

  if (loading && predictions.length === 0) {
    return (
      <div className="d-flex justify-content-center align-items-center" style={{ minHeight: '400px' }}>
        <Spinner animation="border" role="status" variant="light">
          <span className="visually-hidden">Loading...</span>
        </Spinner>
      </div>
    )
  }

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
          Weather Forecasting System
        </h2>
        <p style={{ color: '#666666', fontSize: '0.875rem', margin: 0 }}>
          Lambda Architecture | Kafka → Spark → Ray | Real-time ML Inference
        </p>
      </div>
      
      {error && (
        <Alert variant="warning" className="mb-4">
          <Alert.Heading>Connection Error</Alert.Heading>
          <p>{error}</p>
          <p className="mb-0" style={{ color: '#666666', fontSize: '0.875rem' }}>
            API endpoint: <code className="code-text">http://localhost:5000</code>
          </p>
        </Alert>
      )}

      <Row className="mb-3">
        <Col md={12}>
          <SystemMetrics 
            predictions={predictions} 
            allStationsData={allStationsData}
            lastUpdate={lastUpdate} 
          />
        </Col>
      </Row>

      {/* Kafka Topics Sections */}
      <Row className="mb-3">
        <Col md={12}>
          <KafkaTopicSection
            title="Weather Raw"
            topicName="weather-raw"
            partitionData={weatherRaw?.partitions || {}}
            loading={topicsLoading}
          />
        </Col>
      </Row>

      <Row className="mb-3">
        <Col md={12}>
          <KafkaTopicSection
            title="Weather Features"
            topicName="weather-features"
            partitionData={weatherFeatures?.partitions || {}}
            loading={topicsLoading}
          />
        </Col>
      </Row>

      <Row className="mb-3">
        <Col md={12}>
          <KafkaTopicSection
            title="Weather Predictions"
            topicName="weather-predictions"
            partitionData={weatherPredictionsTopic?.partitions || {}}
            loading={topicsLoading}
          />
        </Col>
      </Row>

      {/* All Stations Data - Scrollable */}
      <Row className="mb-3">
        <Col md={12}>
          <StationDataList
            stations={allStationsData?.stations || {}}
            loading={topicsLoading}
          />
        </Col>
      </Row>

      {/* System Health & Pipeline Components */}
      <Row className="mb-3">
        <Col md={12}>
          <SystemHealthAndPipeline />
        </Col>
      </Row>
    </div>
  )
}

export default Dashboard
