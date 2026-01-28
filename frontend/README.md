# Weather Forecasting System - Frontend

A modern React + TypeScript frontend for showcasing the Ultimate Stream and Distribute weather forecasting system.

## Features

- **Real-time Dashboard**: Live weather predictions with automatic refresh
- **Interactive Map**: Geographic visualization of weather stations using Leaflet
- **Time Series Charts**: 24-hour forecast visualization using Recharts
- **System Architecture**: Visual representation of the Lambda Architecture
- **Health Monitoring**: Real-time system health status
- **Responsive Design**: Bootstrap-based responsive UI

## Tech Stack

- **React 18** - UI framework
- **TypeScript** - Type safety
- **Vite** - Build tool and dev server
- **Bootstrap 5** - CSS framework
- **React Bootstrap** - Bootstrap components for React
- **Recharts** - Chart library
- **React Leaflet** - Map visualization
- **Axios** - HTTP client

## Prerequisites

- Node.js 18+ and npm/yarn
- Backend API running on port 5000 (see main project README)

## Installation

```bash
cd frontend
npm install
```

## Development

Start the development server:

```bash
npm run dev
```

The frontend will be available at `http://localhost:3000`

The Vite dev server is configured to proxy API requests to `http://localhost:5000`.

## Building for Production

```bash
npm run build
```

The production build will be in the `dist` directory.

## Project Structure

```
frontend/
├── src/
│   ├── components/          # Reusable React components
│   │   ├── Navigation.tsx
│   │   ├── WeatherStationMap.tsx
│   │   ├── PredictionCards.tsx
│   │   └── TimeSeriesChart.tsx
│   ├── pages/              # Page components
│   │   ├── Dashboard.tsx
│   │   ├── Architecture.tsx
│   │   └── SystemHealth.tsx
│   ├── services/           # API service layer
│   │   └── api.ts
│   ├── App.tsx             # Main app component
│   ├── main.tsx            # Entry point
│   └── index.css           # Global styles
├── index.html
├── package.json
├── tsconfig.json
└── vite.config.ts
```

## API Endpoints

The frontend expects the following API endpoints:

- `GET /health` - Health check
- `GET /predictions/latest` - Latest predictions
- `GET /predictions?limit=N` - Get predictions with limit

## Environment Variables

Create a `.env` file in the frontend directory to customize the API URL:

```
VITE_API_URL=http://localhost:5000
```

## Features in Detail

### Dashboard
- Real-time weather predictions from all stations
- Interactive map showing station locations
- 24-hour forecast charts
- Automatic refresh every 30 seconds

### Architecture Page
- Visual representation of the data pipeline
- Component breakdown
- Resource allocation information
- Links to monitoring dashboards

### System Health Page
- API service status
- Component health indicators
- Links to Spark and Ray dashboards
- Automatic health checks every 10 seconds

## Troubleshooting

### API Connection Issues

If you see "Failed to fetch predictions":
1. Ensure the backend API is running: `docker compose up api`
2. Check API health: `curl http://localhost:5000/health`
3. Verify CORS settings if accessing from a different origin

### Map Not Displaying

The map uses Leaflet which requires CSS. Ensure the Leaflet CSS is loaded in `index.html`.

### Build Errors

If you encounter TypeScript errors:
- Run `npm install` to ensure all dependencies are installed
- Check Node.js version (requires 18+)
- Clear node_modules and reinstall: `rm -rf node_modules && npm install`

## License

Part of the Ultimate Stream and Distribute project.
