import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { WeatherPrediction } from '../services/api'

interface TimeSeriesChartProps {
  predictions: WeatherPrediction[]
}

function TimeSeriesChart({ predictions }: TimeSeriesChartProps) {
  if (predictions.length === 0) {
    return <p className="text-muted">No data available for chart</p>
  }

  // Prepare data for the first prediction with temperature data
  const predictionWithTemp = predictions.find(
    (p) => p.predictions?.temperature && p.predictions.temperature.length > 0
  )

  if (!predictionWithTemp || !predictionWithTemp.predictions?.temperature) {
    return <p className="text-muted">No temperature forecast data available</p>
  }

  // Generate time labels for 24-hour forecast (assuming hourly predictions)
  const hours = predictionWithTemp.predictions.temperature.length
  const chartData = Array.from({ length: hours }, (_, i) => {
    const now = new Date(predictionWithTemp.timestamp)
    const futureTime = new Date(now.getTime() + i * 60 * 60 * 1000) // Add i hours
    
    return {
      time: futureTime.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }),
      hour: i,
      temperature: predictionWithTemp.predictions.temperature[i],
      humidity: predictionWithTemp.predictions.humidity?.[i],
      pressure: predictionWithTemp.predictions.pressure?.[i],
      windSpeed: predictionWithTemp.predictions.wind_speed?.[i],
    }
  })

  return (
    <ResponsiveContainer width="100%" height={400}>
      <LineChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
        <XAxis 
          dataKey="time" 
          stroke="#666666"
          style={{ fontSize: '11px', fontFamily: 'monospace' }}
        />
        <YAxis 
          stroke="#666666"
          style={{ fontSize: '11px', fontFamily: 'monospace' }}
        />
        <Tooltip 
          contentStyle={{ 
            backgroundColor: '#ffffff', 
            border: '1px solid #e0e0e0',
            color: '#333333',
            fontFamily: 'monospace',
            fontSize: '0.875rem'
          }}
        />
        <Legend 
          wrapperStyle={{ color: '#666666', fontSize: '0.875rem' }}
          iconType="line"
        />
        <Line 
          type="monotone" 
          dataKey="temperature" 
          stroke="#0066cc" 
          strokeWidth={2}
          name="Temperature (°F)"
          dot={{ r: 2, fill: '#0066cc' }}
        />
        {chartData[0].humidity !== undefined && (
          <Line 
            type="monotone" 
            dataKey="humidity" 
            stroke="#28a745" 
            strokeWidth={2}
            name="Humidity (%)"
            dot={{ r: 2, fill: '#28a745' }}
          />
        )}
        {chartData[0].pressure !== undefined && (
          <Line 
            type="monotone" 
            dataKey="pressure" 
            stroke="#ffc107" 
            strokeWidth={2}
            name="Pressure (hPa)"
            dot={{ r: 2, fill: '#ffc107' }}
          />
        )}
        {chartData[0].windSpeed !== undefined && (
          <Line 
            type="monotone" 
            dataKey="windSpeed" 
            stroke="#dc3545" 
            strokeWidth={2}
            name="Wind Speed (m/s)"
            dot={{ r: 2, fill: '#dc3545' }}
          />
        )}
      </LineChart>
    </ResponsiveContainer>
  )
}

export default TimeSeriesChart
