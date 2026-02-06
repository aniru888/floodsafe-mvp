# FHI Quick Reference Card

## Formula
```
FHI = (0.35×P + 0.18×I + 0.12×S + 0.12×A + 0.08×R + 0.15×E) × T
```

## Components
- **P (35%)**: Precipitation forecast
- **I (18%)**: Intensity (hourly max)
- **S (12%)**: Soil saturation
- **A (12%)**: Antecedent conditions
- **R (8%)**: Runoff potential
- **E (15%)**: Elevation risk
- **T**: Monsoon modifier (1.2 Jun-Sep, else 1.0)

## Risk Levels
| Score | Level | Color |
|-------|-------|-------|
| 0.0-0.2 | Low | Green |
| 0.2-0.4 | Moderate | Yellow |
| 0.4-0.7 | High | Orange |
| 0.7-1.0 | Extreme | Red |

## API Usage

### All Hotspots
```bash
GET /api/ml/hotspots/all?include_fhi=true
```

### Single Hotspot
```bash
GET /api/ml/hotspots/hotspot/{id}?include_fhi=true
```

### Disable FHI (Faster)
```bash
GET /api/ml/hotspots/all?include_fhi=false
```

## Response Fields
- `fhi_score`: 0.0-1.0
- `fhi_level`: "low" | "moderate" | "high" | "extreme"
- `fhi_color`: Hex color code
- `elevation_m`: Elevation in meters
- `components`: {P, I, S, A, R, E} breakdown (single hotspot only)

## Performance
- **First call**: ~500ms (API fetch)
- **Cached**: <1ms
- **Cache TTL**: 1 hour

## Testing
```bash
cd apps/ml-service
python test_fhi_integration.py
```

## Files
- **Calculator**: `src/data/fhi_calculator.py`
- **Integration**: `src/api/hotspots.py`
- **Test**: `test_fhi_integration.py`
- **Guide**: `FHI_INTEGRATION_GUIDE.md`
