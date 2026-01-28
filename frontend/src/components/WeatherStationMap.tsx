import { useEffect, useRef } from 'react'
import { MapContainer, TileLayer, Marker, Popup } from 'react-leaflet'
import L from 'leaflet'
import { WeatherPrediction } from '../services/api'

// Fix for default marker icon in React-Leaflet
delete (L.Icon.Default.prototype as any)._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
})

interface WeatherStationMapProps {
  predictions: WeatherPrediction[]
}

// Station coordinates (approximate locations for major US weather stations)
const STATION_COORDINATES: Record<string, [number, number]> = {
  KMSN: [43.1399, -89.3375], // Madison, WI
  KMKE: [42.9472, -87.8967], // Milwaukee, WI
  KMDW: [41.7868, -87.7522], // Chicago, IL
  KMSP: [44.8833, -93.2219], // Minneapolis, MN
  KDSM: [41.5340, -93.6631], // Des Moines, IA
}

function WeatherStationMap({ predictions }: WeatherStationMapProps) {
  const mapRef = useRef<L.Map | null>(null)

  // Get unique stations from predictions
  const stations = Array.from(
    new Set(predictions.map((p) => p.station_id))
  ).map((stationId) => {
    const stationPred = predictions.find((p) => p.station_id === stationId)
    return {
      id: stationId,
      name: stationPred?.station_name || stationId,
      coordinates: STATION_COORDINATES[stationId] || [40.0, -90.0],
      prediction: stationPred,
    }
  })

  const center: [number, number] = stations.length > 0 
    ? stations[0].coordinates 
    : [42.0, -87.0]

  return (
    <MapContainer
      center={center}
      zoom={5}
      style={{ height: '400px', width: '100%' }}
      ref={mapRef}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {stations.map((station) => (
        <Marker key={station.id} position={station.coordinates}>
          <Popup>
            <div>
              <strong>{station.name}</strong>
              <br />
              <small>Station ID: {station.id}</small>
              {station.prediction && (
                <>
                  <br />
                  <small>
                    Last Update: {new Date(station.prediction.timestamp).toLocaleString()}
                  </small>
                  {station.prediction.predictions?.temperature && (
                    <>
                      <br />
                      <strong>
                        Temp: {station.prediction.predictions.temperature[0]?.toFixed(1)}°F
                      </strong>
                    </>
                  )}
                </>
              )}
            </div>
          </Popup>
        </Marker>
      ))}
    </MapContainer>
  )
}

export default WeatherStationMap
