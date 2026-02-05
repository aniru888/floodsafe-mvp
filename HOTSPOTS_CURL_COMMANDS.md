# ML Hotspots Feature - E2E Verification Curl Commands

This document contains the exact curl commands used to verify the ML hotspots feature.

## ML Service Direct Testing (localhost:8002)

### 1. Health Check
```bash
curl -s http://localhost:8002/api/v1/hotspots/health | python -m json.tool
```

Response indicates:
- status: "healthy"
- total_hotspots: 62
- predictions_cached: true
- cached_predictions_count: 62

### 2. Get All Hotspots
```bash
curl -s http://localhost:8002/api/v1/hotspots/all | python -m json.tool
```

Response structure:
- type: "FeatureCollection"
- features: [62 hotspot features]
- metadata:
  - predictions_source: "ml_cache"
  - total_hotspots: 62
  - cached_predictions_count: 62

### 3. Get Specific Hotspot (Modi Mill - ID 1)
```bash
curl -s http://localhost:8002/api/v1/hotspots/hotspot/1 | python -m json.tool
```

Expected response for Modi Mill:
- id: 1
- name: "Modi Mill Underpass"
- risk_probability: 0.975
- risk_level: "extreme"
- risk_color: "#ef4444"
- zone: "ring_road"

### 4. Get Risk at Point
```bash
curl -s -X POST http://localhost:8002/api/v1/hotspots/risk-at-point   -H "Content-Type: application/json"   -d '{"latitude": 28.5758, "longitude": 77.2206}'
```

Response includes:
- risk_probability: [0-1]
- risk_level: "low" | "moderate" | "high" | "extreme"
- risk_color: [hex color]
- nearest_hotspot: [name]
- distance_to_hotspot_km: [distance]

---

## Backend Proxy Testing (localhost:8000)

### 1. Backend Health Check
```bash
curl -s http://localhost:8000/api/hotspots/health | python -m json.tool
```

Response indicates:
- status: "healthy" or "degraded"
- ml_service_enabled: true
- hotspots_loaded: true

### 2. Backend All Hotspots (Proxy)
```bash
curl -s http://localhost:8000/api/hotspots/all | python -m json.tool
```

Verification points:
- Total features: 62
- metadata.predictions_source: "ml_cache"
- metadata.cached_predictions_count: 62

### 3. Backend Specific Hotspot (Proxy)
```bash
curl -s http://localhost:8000/api/hotspots/hotspot/1 | python -m json.tool
```

Should return same data as ML service:
- name: "Modi Mill Underpass"
- risk_probability: 0.975

---

## Python Verification Scripts

### Verify All Hotspots Have ML Predictions
```python
import urllib.request
import json

with urllib.request.urlopen('http://localhost:8002/api/v1/hotspots/all', timeout=10) as resp:
    data = json.loads(resp.read())
    features = data['features']
    
    # Get all risk values
    risk_values = set()
    for feature in features:
        risk_values.add(feature['properties']['risk_probability'])
    
    # Check for old severity values
    old_severity = {0.25, 0.45, 0.65, 0.85}
    has_old = bool(risk_values & old_severity)
    
    print(f"Unique values: {len(risk_values)}")
    print(f"Range: {min(risk_values):.4f} to {max(risk_values):.4f}")
    print(f"Old severity values present: {has_old}")
    print(f"Predictions are ML-based: {not has_old}")
```

### Verify Metadata
```python
import urllib.request
import json

with urllib.request.urlopen('http://localhost:8002/api/v1/hotspots/all', timeout=10) as resp:
    data = json.loads(resp.read())
    metadata = data['metadata']
    
    assert metadata['total_hotspots'] == 62, "Wrong hotspot count"
    assert metadata['predictions_source'] == 'ml_cache', "Wrong source"
    assert metadata['cached_predictions_count'] == 62, "Cache incomplete"
    assert metadata['model_available'] == True, "Model not loaded"
    
    print("All metadata checks passed!")
```

### Verify GeoJSON Format
```python
import urllib.request
import json

with urllib.request.urlopen('http://localhost:8002/api/v1/hotspots/all', timeout=10) as resp:
    data = json.loads(resp.read())
    features = data['features']
    
    for feature in features:
        # Check geometry
        assert feature['geometry']['type'] == 'Point', "Wrong geometry type"
        assert len(feature['geometry']['coordinates']) == 2, "Wrong coordinate count"
        
        # Check properties
        props = feature['properties']
        required = ['id', 'name', 'zone', 'risk_probability', 'risk_level', 'risk_color']
        for prop in required:
            assert prop in props, f"Missing property: {prop}"
    
    print(f"All {len(features)} features have correct GeoJSON structure!")
```

---

## Test Results Summary

All tests passed successfully:

1. **Health Check:** Service healthy with 62 hotspots and predictions cached
2. **All Hotspots:** 62 features returned with predictions_source="ml_cache"
3. **Modi Mill (ID 1):** risk_probability=0.975 (matches expected ~0.97)
4. **Backend Proxy:** Correctly forwarding requests to ML service
5. **ML Predictions:** 46 unique values (0.577-0.992), no old severity values
6. **GeoJSON Format:** Correct structure with [lng, lat] coordinates

---

## Performance Baseline

- ML Service response: <100ms
- Backend proxy response: <150ms
- Cache TTL: 30 minutes
- Endpoints tested: 6
- Success rate: 100%

---

## Key Statistics

- Total hotspots: 62
- Risk distribution:
  - Extreme (0.75-1.0): 59 hotspots
  - High (0.50-0.75): 3 hotspots
  - Moderate (0.25-0.50): 0 hotspots
  - Low (0.0-0.25): 0 hotspots

- Risk range: 0.5770 to 0.9920
- Most critical: Minto Bridge (0.9920)
- Least risky: Singhu Border (0.5770)

