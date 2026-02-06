"""Verify the extracted Delhi flood GeoJSON data."""
import json
from pathlib import Path

DATA_PATH = Path(__file__).parent.parent / "data" / "delhi_historical_floods.json"

with open(DATA_PATH) as f:
    data = json.load(f)

print(f"Total events: {data['metadata']['total_events']}")
print("\nMetadata:")
for key, value in data['metadata'].items():
    print(f"  {key}: {value}")

print("\n" + "="*60)
print("First 3 events:")
print("="*60)

for i, feature in enumerate(data['features'][:3], 1):
    props = feature['properties']
    coords = feature['geometry']['coordinates']
    print(f"\nEvent {i}:")
    print(f"  ID: {props['id']}")
    print(f"  Date: {props['date']}")
    print(f"  Year: {props['year']}")
    print(f"  Districts: {props['districts']}")
    print(f"  Severity: {props['severity']}")
    print(f"  Coordinates: {coords}")
    print(f"  Fatalities: {props['fatalities']}")
    print(f"  Injured: {props['injured']}")
    print(f"  Displaced: {props['displaced']}")
    print(f"  Duration: {props['duration_days']} days")
    print(f"  Main Cause: {props['main_cause']}")

print("\n" + "="*60)
print("Events by year:")
print("="*60)

# Count events by year
year_counts = {}
for feature in data['features']:
    year = feature['properties']['year']
    if year:
        year_counts[year] = year_counts.get(year, 0) + 1

for year in sorted(year_counts.keys()):
    print(f"  {year}: {year_counts[year]} events")

print("\n" + "="*60)
print("Events by severity:")
print("="*60)

severity_counts = {}
for feature in data['features']:
    severity = feature['properties']['severity']
    severity_counts[severity] = severity_counts.get(severity, 0) + 1

for severity, count in sorted(severity_counts.items()):
    print(f"  {severity}: {count} events")
