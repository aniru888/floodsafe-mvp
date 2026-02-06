"""
Extract Delhi NCR flood events from IFI-Impacts dataset.

Outputs GeoJSON for FloodAtlas visualization.
"""
import json
import pandas as pd
from pathlib import Path
from datetime import datetime

DATA_DIR = Path(__file__).parent.parent / "data"
IFI_PATH = DATA_DIR / "external" / "ifi_impacts" / "India_Flood_Inventory_v3.csv"
OUTPUT_PATH = DATA_DIR / "delhi_historical_floods.json"

# Delhi NCR districts (variations to match IFI data)
DELHI_DISTRICTS = [
    "Delhi", "New Delhi", "North Delhi", "South Delhi", "East Delhi",
    "West Delhi", "Central Delhi", "North West Delhi", "North East Delhi",
    "South West Delhi", "South East Delhi", "Shahdara",
    # NCR districts
    "Gurgaon", "Gurugram", "Faridabad", "Noida", "Ghaziabad", "Gautam Buddha Nagar"
]

# District centroid coordinates (approximate)
DISTRICT_CENTROIDS = {
    "Delhi": (28.6139, 77.2090),
    "New Delhi": (28.6139, 77.2090),
    "North Delhi": (28.7041, 77.2025),
    "South Delhi": (28.5355, 77.2500),
    "East Delhi": (28.6280, 77.2950),
    "West Delhi": (28.6570, 77.0590),
    "Central Delhi": (28.6450, 77.2180),
    "North West Delhi": (28.7150, 77.1020),
    "North East Delhi": (28.6920, 77.2650),
    "South West Delhi": (28.5820, 77.0520),
    "South East Delhi": (28.5630, 77.2680),
    "Shahdara": (28.6730, 77.2890),
    "Gurgaon": (28.4595, 77.0266),
    "Gurugram": (28.4595, 77.0266),
    "Faridabad": (28.4089, 77.3178),
    "Noida": (28.5355, 77.3910),
    "Ghaziabad": (28.6692, 77.4538),
    "Gautam Buddha Nagar": (28.4744, 77.5040),
}

def load_ifi_data():
    """Load IFI dataset and explore structure."""
    df = pd.read_csv(IFI_PATH)
    print(f"Total records: {len(df)}")
    print(f"Columns: {list(df.columns)}")
    return df

def filter_delhi_floods(df: pd.DataFrame) -> pd.DataFrame:
    """Filter for Delhi NCR flood events."""
    # Filter by State column (contains "Delhi")
    if 'State' in df.columns:
        delhi_mask = df['State'].str.contains('Delhi', case=False, na=False)
        delhi_df = df[delhi_mask].copy()
        print(f"Delhi NCR floods: {len(delhi_df)} events")
        return delhi_df
    else:
        print("Warning: No 'State' column found. Available columns:", df.columns.tolist())
        return pd.DataFrame()

def create_geojson(delhi_df: pd.DataFrame) -> dict:
    """Convert Delhi floods to GeoJSON."""
    features = []

    for idx, row in delhi_df.iterrows():
        # Get coordinates - use IFI's Latitude/Longitude if available
        lat = row.get('Latitude')
        lon = row.get('Longitude')

        # Fall back to Delhi centroid if coordinates missing
        if pd.isna(lat) or pd.isna(lon):
            lat, lon = 28.6139, 77.2090

        # Parse date from "Start Date" column
        date_str = str(row.get('Start Date', ''))
        if date_str and date_str != 'nan':
            # Parse date format "01-08-1969 00:00" to "1969-08-01"
            try:
                parts = date_str.split()[0].split('-')
                if len(parts) == 3:
                    day, month, year = parts
                    date_str = f"{year}-{month}-{day}"
            except:
                pass

        # Get district info
        districts = str(row.get('Districts', 'Delhi'))

        # Extract severity based on IFI's Severity column and fatalities
        severity_val = row.get('Severity', '')
        fatalities = row.get('Human fatality', 0)

        # Map IFI severity to our categories
        if pd.notna(fatalities) and fatalities > 10:
            severity = "severe"
        elif pd.notna(fatalities) and fatalities > 0:
            severity = "moderate"
        elif severity_val and 'high' in str(severity_val).lower():
            severity = "severe"
        elif severity_val and 'moderate' in str(severity_val).lower():
            severity = "moderate"
        else:
            severity = "minor"

        # Get additional metadata
        duration = row.get('Duration(Days)', '')
        main_cause = row.get('Main Cause', '')
        area_affected = row.get('Area Affected', '')
        injured = row.get('Human injured', 0)
        displaced = row.get('Human Displaced', 0)

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [float(lon), float(lat)]  # GeoJSON: [lng, lat]
            },
            "properties": {
                "id": f"ifi_{row.get('UEI', idx)}",
                "date": date_str,
                "districts": districts,
                "severity": severity,
                "source": "IFI-Impacts",
                "year": int(date_str[:4]) if len(date_str) >= 4 and date_str[:4].isdigit() else None,
                "fatalities": int(fatalities) if pd.notna(fatalities) else 0,
                "injured": int(injured) if pd.notna(injured) else 0,
                "displaced": int(displaced) if pd.notna(displaced) else 0,
                "duration_days": int(duration) if pd.notna(duration) and str(duration).replace('.', '').isdigit() else None,
                "main_cause": main_cause if pd.notna(main_cause) else "",
                "area_affected": area_affected if pd.notna(area_affected) else ""
            }
        }
        features.append(feature)

    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "source": "India Flood Inventory (IFI-Impacts)",
            "source_url": "https://zenodo.org/records/11275211",
            "coverage": "1967-2023",
            "region": "Delhi NCR",
            "total_events": len(features),
            "generated_at": datetime.now().isoformat()
        }
    }

def main():
    # Load data
    df = load_ifi_data()

    # Filter Delhi
    delhi_df = filter_delhi_floods(df)

    if len(delhi_df) == 0:
        print("No Delhi floods found. Creating empty GeoJSON.")

    # Create GeoJSON
    geojson = create_geojson(delhi_df)

    # Save
    with open(OUTPUT_PATH, 'w') as f:
        json.dump(geojson, f, indent=2)

    print(f"Saved: {OUTPUT_PATH}")
    print(f"Total Delhi flood events: {len(geojson['features'])}")

if __name__ == "__main__":
    main()
