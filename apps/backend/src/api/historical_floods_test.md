# Historical Floods API Documentation

## Overview
Endpoint for serving historical flood events from the IFI-Impacts dataset for FloodAtlas visualization.

**Base URL:** `/api/historical-floods`

## Endpoints

### 1. GET `/api/historical-floods`
Get historical flood events for a city as GeoJSON FeatureCollection.

**Query Parameters:**
- `city` (string, default: "delhi") - City name (currently only Delhi supported)
- `min_year` (int, optional) - Filter events from this year onwards
- `max_year` (int, optional) - Filter events up to this year
- `severity` (string, optional) - Filter by severity: "minor", "moderate", "severe"

**Response:**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Point",
        "coordinates": [77.209, 28.6139]
      },
      "properties": {
        "id": "ifi_UEI-IMD-FL-2023-0600",
        "date": "2023-07-09",
        "districts": "West",
        "severity": "minor",
        "source": "IFI-Impacts",
        "year": 2023,
        "fatalities": 0,
        "injured": 2,
        "displaced": 0,
        "duration_days": 1,
        "main_cause": "Heavy Rains & Floods (Yamuna River)",
        "area_affected": ""
      }
    }
  ],
  "metadata": {
    "source": "India Flood Inventory (IFI-Impacts)",
    "coverage": "1967-2023",
    "region": "Delhi NCR",
    "total_events": 45,
    "generated_at": "2025-12-12T06:29:47.811905"
  }
}
```

**Example Requests:**
```bash
# Get all Delhi historical floods
curl "http://localhost:8000/api/historical-floods?city=delhi"

# Get floods from 2010 onwards
curl "http://localhost:8000/api/historical-floods?city=delhi&min_year=2010"

# Get only severe floods
curl "http://localhost:8000/api/historical-floods?city=delhi&severity=severe"

# Get moderate floods from 2015-2020
curl "http://localhost:8000/api/historical-floods?city=delhi&min_year=2015&max_year=2020&severity=moderate"

# Request unsupported city (returns empty with message)
curl "http://localhost:8000/api/historical-floods?city=bangalore"
```

---

### 2. GET `/api/historical-floods/stats`
Get aggregated statistics about historical floods.

**Query Parameters:**
- `city` (string, default: "delhi") - City name

**Response:**
```json
{
  "city": "Delhi NCR",
  "available": true,
  "total_events": 45,
  "year_range": {
    "min": 1969,
    "max": 2023
  },
  "severity_breakdown": {
    "minor": 38,
    "moderate": 5,
    "severe": 2,
    "unknown": 0
  },
  "casualties": {
    "total_fatalities": 12,
    "total_injured": 25,
    "total_displaced": 1500
  },
  "districts_affected_count": 45,
  "source": "India Flood Inventory (IFI-Impacts)",
  "metadata": {
    "source": "India Flood Inventory (IFI-Impacts)",
    "coverage": "1967-2023"
  }
}
```

**Example Request:**
```bash
curl "http://localhost:8000/api/historical-floods/stats?city=delhi"
```

---

### 3. GET `/api/historical-floods/health`
Health check for the historical floods service.

**Response:**
```json
{
  "status": "ok",
  "service": "historical-floods",
  "data_available": true,
  "supported_cities": ["delhi", "delhi ncr", "new delhi"],
  "data_path": "/path/to/ml-service/data/delhi_historical_floods.json"
}
```

**Example Request:**
```bash
curl "http://localhost:8000/api/historical-floods/health"
```

---

## Error Responses

### 503 Service Unavailable
Data file not yet generated:
```json
{
  "detail": "Historical floods data not yet generated. Run ml-service preprocessing scripts first."
}
```

### 500 Internal Server Error
Error reading/parsing data:
```json
{
  "detail": "Error parsing historical floods data: <error message>"
}
```

---

## Data Schema

### Feature Properties
- `id` (string) - Unique event identifier from IFI dataset
- `date` (string) - Event date in ISO format (YYYY-MM-DD)
- `districts` (string) - Comma-separated list of affected districts
- `severity` (string) - "minor", "moderate", or "severe"
- `source` (string) - Data source (currently "IFI-Impacts")
- `year` (int) - Year of event
- `fatalities` (int) - Number of deaths
- `injured` (int) - Number of people injured
- `displaced` (int) - Number of people displaced
- `duration_days` (int) - Duration of event in days
- `main_cause` (string) - Primary cause of flooding
- `area_affected` (string) - Description of affected area

### GeoJSON Coordinates
Format: `[longitude, latitude]` (GeoJSON standard)

---

## Integration with Frontend

### Example Usage in React/TypeScript
```typescript
// Fetch historical floods
const response = await fetchJson<HistoricalFloodsResponse>(
  `/api/historical-floods?city=delhi&min_year=2010`
);

// Add to MapLibre GL
map.addSource('historical-floods', {
  type: 'geojson',
  data: response
});

// Add layer
map.addLayer({
  id: 'historical-floods-points',
  type: 'circle',
  source: 'historical-floods',
  paint: {
    'circle-radius': [
      'match',
      ['get', 'severity'],
      'severe', 8,
      'moderate', 6,
      'minor', 4,
      4
    ],
    'circle-color': [
      'match',
      ['get', 'severity'],
      'severe', '#dc2626',
      'moderate', '#f59e0b',
      'minor', '#fbbf24',
      '#fbbf24'
    ],
    'circle-opacity': 0.7
  }
});
```

---

## Multi-City Support

Currently only Delhi NCR is supported. For unsupported cities, the API returns:
```json
{
  "type": "FeatureCollection",
  "features": [],
  "metadata": {
    "message": "Historical flood data not yet available for bangalore. Coming soon!",
    "total_events": 0
  }
}
```

This allows the frontend to gracefully handle missing data and display a "Coming Soon" message.

---

## Data Source

**India Flood Inventory (IFI-Impacts)**
- Source URL: https://zenodo.org/records/11275211
- Coverage: 1967-2023
- Region: India (Delhi NCR extracted)
- Total Events (Delhi): 45

---

## Testing

### Manual Testing
```bash
# Start backend
cd apps/backend
python -m uvicorn src.main:app --reload

# Test endpoints
curl http://localhost:8000/api/historical-floods/health
curl http://localhost:8000/api/historical-floods?city=delhi
curl http://localhost:8000/api/historical-floods/stats?city=delhi
```

### Expected Results
- Health check should return `"data_available": true`
- Default query should return 45 events for Delhi
- Stats should show year range 1969-2023
- Coordinates should be in [longitude, latitude] format
