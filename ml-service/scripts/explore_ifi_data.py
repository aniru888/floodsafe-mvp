"""
Interactive exploration of IFI-Impacts Delhi flood data.

Usage:
    python scripts/explore_ifi_data.py --year 2023
    python scripts/explore_ifi_data.py --severity severe
    python scripts/explore_ifi_data.py --casualties
"""
import json
import argparse
from pathlib import Path

DATA_PATH = Path(__file__).parent.parent / "data" / "delhi_historical_floods.json"

def load_data():
    with open(DATA_PATH) as f:
        return json.load(f)

def filter_by_year(features, year):
    return [f for f in features if f['properties']['year'] == year]

def filter_by_severity(features, severity):
    return [f for f in features if f['properties']['severity'] == severity]

def filter_by_casualties(features):
    return [f for f in features if f['properties']['fatalities'] > 0]

def print_event(feature):
    p = feature['properties']
    coords = feature['geometry']['coordinates']

    print(f"\nEvent ID: {p['id']}")
    print(f"Date: {p['date']} (Year: {p['year']})")
    print(f"Location: [{coords[1]:.4f}, {coords[0]:.4f}]")
    print(f"Districts: {p['districts']}")
    print(f"Severity: {p['severity'].upper()}")
    print(f"Duration: {p['duration_days']} days")
    print(f"Main Cause: {p['main_cause']}")

    if p['fatalities'] > 0 or p['injured'] > 0 or p['displaced'] > 0:
        print(f"\nImpact:")
        print(f"  Fatalities: {p['fatalities']}")
        print(f"  Injured: {p['injured']}")
        print(f"  Displaced: {p['displaced']}")

    if p['area_affected']:
        print(f"Area Affected: {p['area_affected']}")

    print("-" * 80)

def main():
    parser = argparse.ArgumentParser(description='Explore Delhi flood data from IFI-Impacts')
    parser.add_argument('--year', type=int, help='Filter by year (e.g., 2023)')
    parser.add_argument('--severity', choices=['minor', 'moderate', 'severe'], help='Filter by severity')
    parser.add_argument('--casualties', action='store_true', help='Show only events with fatalities')
    parser.add_argument('--stats', action='store_true', help='Show statistics only')

    args = parser.parse_args()

    data = load_data()
    features = data['features']

    # Apply filters
    if args.year:
        features = filter_by_year(features, args.year)
        print(f"Filtering by year: {args.year}")

    if args.severity:
        features = filter_by_severity(features, args.severity)
        print(f"Filtering by severity: {args.severity}")

    if args.casualties:
        features = filter_by_casualties(features)
        print("Filtering by casualties")

    print(f"\nTotal events matching criteria: {len(features)}")
    print("=" * 80)

    if args.stats:
        # Show statistics
        total_fatalities = sum(f['properties']['fatalities'] for f in features)
        total_injured = sum(f['properties']['injured'] for f in features)
        total_displaced = sum(f['properties']['displaced'] for f in features)

        print(f"\nStatistics:")
        print(f"  Total Events: {len(features)}")
        print(f"  Total Fatalities: {total_fatalities}")
        print(f"  Total Injured: {total_injured}")
        print(f"  Total Displaced: {total_displaced}")

        # By severity
        severity_counts = {}
        for f in features:
            sev = f['properties']['severity']
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        print(f"\nBy Severity:")
        for sev, count in sorted(severity_counts.items()):
            print(f"  {sev}: {count}")

        # By year
        year_counts = {}
        for f in features:
            year = f['properties']['year']
            if year:
                year_counts[year] = year_counts.get(year, 0) + 1

        print(f"\nBy Year:")
        for year in sorted(year_counts.keys()):
            print(f"  {year}: {year_counts[year]}")
    else:
        # Print individual events
        for feature in features:
            print_event(feature)

if __name__ == "__main__":
    main()
