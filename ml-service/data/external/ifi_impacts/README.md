# India Flood Inventory (IFI-Impacts) Dataset

## Source
**Zenodo Repository**: https://zenodo.org/records/11275211
**License**: CC-BY 4.0
**Coverage**: 1967-2023
**Total Records**: 6,876 flood events across India

## Citation
```
India Flood Inventory (IFI-Impacts) v3.0
Authors: [Citation from Zenodo]
DOI: 10.5281/zenodo.11275211
```

## Files
- `India_Flood_Inventory_v3.csv` (1.8 MB) - Main flood events dataset

## Schema
| Column | Description |
|--------|-------------|
| UEI | Unique Event Identifier |
| Start Date | Flood start date (DD-MM-YYYY HH:MM) |
| End Date | Flood end date |
| Duration(Days) | Event duration in days |
| Main Cause | Primary flood cause (e.g., heavy rains, river overflow) |
| Location | Textual location description |
| Districts | Comma-separated list of affected districts |
| State | Indian state |
| Latitude | Centroid latitude (WGS84) |
| Longitude | Centroid longitude (WGS84) |
| Severity | IFI severity classification |
| Area Affected | Affected area description |
| Human fatality | Number of deaths |
| Human injured | Number of injured |
| Human Displaced | Number of displaced persons |
| Animal Fatality | Livestock casualties |
| Description of Casualties/injured | Textual description |
| Extent of damage | Damage description |
| Event Source | Original data source |
| Event Souce ID | Source identifier |
| District_LGD_Codes | Government district codes |
| State_Codes | State codes |

## Delhi NCR Statistics
**Total Delhi floods**: 45 events (1969-2023)

### By Severity
- Minor: 15 events
- Moderate: 29 events
- Severe: 1 event

### Notable Years
- 2023: 3 events (most recent)
- 1995: 3 events
- 1993: 3 events
- 1978: 3 events

### Data Gaps
- Missing data: 1998-2002, 2004-2008, 2012, 2014-2019
- Limited coordinate precision (district-level centroids)

## Processing
See `apps/ml-service/scripts/`:
- `08_download_ifi_impacts.py` - Download from Zenodo
- `09_extract_delhi_floods.py` - Extract Delhi events to GeoJSON
- `verify_delhi_floods.py` - Verify output data

## Output
**GeoJSON**: `apps/ml-service/data/delhi_historical_floods.json`

Format:
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
        "id": "ifi_UEI-IMD-FL-1969-0005",
        "date": "1969-08-01",
        "year": 1969,
        "districts": "New Delhi, ...",
        "severity": "moderate",
        "fatalities": 0,
        "injured": 0,
        "displaced": 0,
        "duration_days": 22,
        "main_cause": "heavy rains",
        "area_affected": "..."
      }
    }
  ],
  "metadata": {
    "source": "India Flood Inventory (IFI-Impacts)",
    "total_events": 45,
    "coverage": "1967-2023",
    "region": "Delhi NCR"
  }
}
```

## Usage in FloodSafe
This historical data will be used for:
1. **FloodAtlas visualization** - Display past flood events on map
2. **Model validation** - Ground truth for LSTM predictions
3. **Risk mapping** - Identify flood-prone areas
4. **Trend analysis** - Study flood frequency patterns
