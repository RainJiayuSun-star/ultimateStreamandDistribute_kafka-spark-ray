import axios from 'axios'

// Use direct URL since CORS is enabled on the API
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000'

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    'Content-Type': 'application/json',
  },
})

export interface WeatherPrediction {
  station_id: string
  station_name?: string
  timestamp: string
  predictions?: {
    temperature?: number[]
    humidity?: number[]
    pressure?: number[]
    wind_speed?: number[]
  }
  anomaly?: {
    is_anomaly: boolean
    score?: number
  }
  confidence?: number
  partition?: number
}

export interface HealthStatus {
  status: string
  service: string
}

export interface PredictionsResponse {
  predictions: WeatherPrediction[]
  count: number
}

export interface MessageData {
  offset: number
  timestamp: string
  data: any
}

export interface TopicResponse {
  topic: string
  partitions: { [partition: number]: MessageData[] }
  count: number
}

export interface AllStationsResponse {
  stations: { [stationId: string]: any }
  timestamp: string
}

class ApiService {
  async getHealth(): Promise<HealthStatus> {
    const response = await api.get<HealthStatus>('/health')
    return response.data
  }

  async getLatestPredictions(): Promise<PredictionsResponse> {
    try {
      const response = await api.get<PredictionsResponse>('/predictions/latest')
      return response.data
    } catch (error: any) {
      // Handle 404 "No predictions available" as empty result, not an error
      if (error.response?.status === 404) {
        return { predictions: [], count: 0 }
      }
      throw error
    }
  }

  async getPredictions(limit: number = 10): Promise<PredictionsResponse> {
    try {
      const response = await api.get<PredictionsResponse>('/predictions', {
        params: { limit },
      })
      return response.data
    } catch (error: any) {
      // Handle 404 as empty result
      if (error.response?.status === 404) {
        return { predictions: [], count: 0 }
      }
      throw error
    }
  }

  async getWeatherRaw(): Promise<TopicResponse> {
    try {
      const response = await api.get<TopicResponse>('/topics/weather-raw')
      return response.data
    } catch (error: any) {
      if (error.response?.status === 404) {
        return { topic: 'weather-raw', partitions: {}, count: 0 }
      }
      throw error
    }
  }

  async getWeatherFeatures(): Promise<TopicResponse> {
    try {
      const response = await api.get<TopicResponse>('/topics/weather-features')
      return response.data
    } catch (error: any) {
      if (error.response?.status === 404) {
        return { topic: 'weather-features', partitions: {}, count: 0 }
      }
      throw error
    }
  }

  async getWeatherPredictionsTopic(): Promise<TopicResponse> {
    try {
      const response = await api.get<TopicResponse>('/topics/weather-predictions')
      return response.data
    } catch (error: any) {
      if (error.response?.status === 404) {
        return { topic: 'weather-predictions', partitions: {}, count: 0 }
      }
      throw error
    }
  }

  async getAllStationsData(): Promise<AllStationsResponse> {
    try {
      const response = await api.get<AllStationsResponse>('/stations/all')
      return response.data
    } catch (error: any) {
      if (error.response?.status === 404) {
        return { stations: {}, timestamp: new Date().toISOString() }
      }
      throw error
    }
  }
}

export default new ApiService()
