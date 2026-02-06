# Flood Hazard Index (FHI) Integration Guide

## Overview

The Flood Hazard Index (FHI) is now integrated into the ML service hotspots API. Each hotspot returns a live FHI score calculated using real-time weather data from Open-Meteo.

## FHI Formula

```
FHI = (0.35×P + 0.18×I + 0.12×S + 0.12×A + 0.08×R + 0.15×E) × T_modifier
```

### Components (0.0 - 1.0)

| Component | Weight | Description | Data Source |
|-----------|--------|-------------|-------------|
| **P** | 35% | Precipitation forecast (weighted 24h/48h/72h) | Open-Meteo hourly precipitation |
| **I** | 18% | Intensity (hourly max) | Open-Meteo hourly precipitation |
| **S** | 12% | Soil Saturation | Open-Meteo soil_moisture_0_to_7cm |
| **A** | 12% | Antecedent conditions (3-day total) | Open-Meteo cumulative precipitation |
| **R** | 8% | Runoff Potential (pressure-based) | Open-Meteo surface_pressure |
| **E** | 15% | Elevation Risk (inverted) | Open-Meteo Elevation API |

### Monsoon Modifier

- **T_modifier = 1.2** during monsoon months (June-September)
- **T_modifier = 1.0** otherwise

## Risk Levels

| FHI Score | Level | Color |
|-----------|-------|-------|
| 0.0 - 0.2 | Low | #22c55e (green) |
| 0.2 - 0.4 | Moderate | #eab308 (yellow) |
| 0.4 - 0.7 | High | #f97316 (orange) |
| 0.7 - 1.0 | Extreme | #ef4444 (red) |

## API Usage

### Get All Hotspots with FHI

```bash
GET /api/ml/hotspots/all?include_fhi=true
```

**Response:**

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Point",
        "coordinates": [77.2090, 28.6139]
      },
      "properties": {
        "id": 1,
        "name": "Connaught Place",
        "zone": "Central",
        "risk_probability": 0.651,
        "risk_level": "high",
        "risk_color": "#f97316",
        "fhi_score": 0.222,
        "fhi_level": "moderate",
        "fhi_color": "#eab308",
        "elevation_m": 219.0
      }
    }
  ],
  "metadata": {
    "fhi_enabled": true,
    "fhi_formula": "FHI = (0.35×P + 0.18×I + 0.12×S + 0.12×A + 0.08×R + 0.15×E) × T_modifier",
    "fhi_components": {
      "P": "Precipitation forecast (35%)",
      "I": "Intensity (hourly max, 18%)",
      "S": "Soil saturation (12%)",
      "A": "Antecedent conditions (12%)",
      "R": "Runoff potential (8%)",
      "E": "Elevation risk (15%)"
    }
  }
}
```

### Get Single Hotspot with FHI

```bash
GET /api/ml/hotspots/hotspot/1?include_fhi=true
```

**Response:**

```json
{
  "id": 1,
  "name": "Connaught Place",
  "lat": 28.6139,
  "lng": 77.2090,
  "zone": "Central",
  "risk_probability": 0.651,
  "risk_level": "high",
  "risk_color": "#f97316",
  "rainfall_factor": 0.0,
  "fhi": {
    "fhi_score": 0.222,
    "fhi_level": "moderate",
    "fhi_color": "#eab308",
    "elevation_m": 219.0,
    "components": {
      "P": 0.000,
      "I": 0.000,
      "S": 0.400,
      "A": 0.000,
      "R": 0.716,
      "E": 0.777
    },
    "monsoon_modifier": 1.0
  }
}
```

### Disable FHI (for faster response)

```bash
GET /api/ml/hotspots/all?include_fhi=false
```

## Implementation Details

### Files Modified

1. **`apps/ml-service/src/data/fhi_calculator.py`** (NEW)
   - `FHICalculator` class
   - `calculate_fhi_for_location()` async function
   - 1-hour cache for FHI results

2. **`apps/ml-service/src/api/hotspots.py`** (UPDATED)
   - Added `include_fhi` query parameter (default: true)
   - Integrated FHI calculation for each hotspot
   - Updated `HotspotRiskResponse` model to include `fhi` field
   - Updated metadata to include FHI documentation

### Caching

- FHI results are cached for **1 hour** per location
- Cache key: `{lat:.4f},{lng:.4f}`
- Reduces Open-Meteo API calls from 2 to 0 for cached locations

### Error Handling

If FHI calculation fails for any reason:

```json
{
  "fhi_score": 0.25,
  "fhi_level": "unknown",
  "fhi_color": "#9ca3af",
  "elevation_m": 220.0
}
```

The hotspot API will **not** fail, it will return default FHI values and log the error.

## Testing

### Run Integration Test

```bash
cd apps/ml-service
python test_fhi_integration.py
```

### Manual Test with cURL

```bash
# Test all hotspots with FHI
curl "http://localhost:8001/api/ml/hotspots/all?include_fhi=true"

# Test single hotspot
curl "http://localhost:8001/api/ml/hotspots/hotspot/1?include_fhi=true"

# Test without FHI (faster)
curl "http://localhost:8001/api/ml/hotspots/all?include_fhi=false"
```

## Data Sources

All FHI data comes from **Open-Meteo** (free, no API key required):

1. **Elevation API**: `https://api.open-meteo.com/v1/elevation`
2. **Forecast API**: `https://api.open-meteo.com/v1/forecast`
   - `hourly=precipitation,soil_moisture_0_to_7cm,surface_pressure`
   - `forecast_days=3`

## Performance

- **Without cache**: ~500-1000ms per hotspot (2 API calls)
- **With cache**: <1ms per hotspot
- **For 62 hotspots**: First call ~30-60s, subsequent calls <100ms
- **Cache TTL**: 1 hour

## Future Enhancements

1. **Batch API calls**: Combine multiple locations in one Open-Meteo request
2. **Redis cache**: Share cache across ML service instances
3. **Historical FHI**: Store FHI time series for trend analysis
4. **FHI alerts**: Trigger notifications when FHI exceeds thresholds
5. **Calibration**: Tune weights based on actual flood events

## References

- Open-Meteo API: https://open-meteo.com/en/docs
- IMD Rainfall Categories: https://imdpune.gov.in/
- Flood Hazard Index research: FloodSafe internal documentation

## Support

For issues or questions:
- Check logs: `apps/ml-service/logs/ml-service.log`
- File issue with FHI tag
- Contact: ML team
