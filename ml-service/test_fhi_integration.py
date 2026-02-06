"""
Test FHI integration with hotspots API.

Run this to verify FHI calculation works end-to-end.
"""

import asyncio
import sys
from pathlib import Path

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# Add parent directory to path to allow imports
sys.path.insert(0, str(Path(__file__).parent))

from src.data.fhi_calculator import FHICalculator, calculate_fhi_for_location


async def test_fhi_calculator():
    """Test FHI calculator with Delhi coordinates."""
    print("\n" + "=" * 60)
    print("Testing FHI Calculator")
    print("=" * 60)

    # Test locations in Delhi
    test_locations = [
        {"name": "Connaught Place", "lat": 28.6292, "lng": 77.2064},
        {"name": "Delhi Railway Station", "lat": 28.6435, "lng": 77.2197},
        {"name": "Minto Bridge", "lat": 28.6289, "lng": 77.2225},
        {"name": "ITO Junction", "lat": 28.6268, "lng": 77.2403},
    ]

    calculator = FHICalculator()

    for location in test_locations:
        print(f"\n{location['name']}")
        print("-" * 60)

        try:
            result = await calculate_fhi_for_location(
                lat=location["lat"],
                lng=location["lng"]
            )

            print(f"  FHI Score:        {result['fhi_score']:.3f}")
            print(f"  FHI Level:        {result['fhi_level']}")
            print(f"  FHI Color:        {result['fhi_color']}")
            print(f"  Elevation:        {result['elevation_m']:.1f} m")
            print(f"  Monsoon Modifier: {result['monsoon_modifier']}")
            print("\n  Components:")
            for comp, value in result['components'].items():
                print(f"    {comp}: {value:.3f}")

            print(f"\n  ✓ SUCCESS")

        except Exception as e:
            print(f"  ✗ FAILED: {e}")

    # Test cache
    print("\n" + "=" * 60)
    print("Testing Cache")
    print("=" * 60)

    print("\nFirst call (should fetch from API)...")
    start = asyncio.get_event_loop().time()
    result1 = await calculate_fhi_for_location(28.6292, 77.2064)
    time1 = (asyncio.get_event_loop().time() - start) * 1000

    print(f"  Time: {time1:.1f}ms")

    print("\nSecond call (should use cache)...")
    start = asyncio.get_event_loop().time()
    result2 = await calculate_fhi_for_location(28.6292, 77.2064)
    time2 = (asyncio.get_event_loop().time() - start) * 1000

    print(f"  Time: {time2:.1f}ms")

    if time2 < time1 / 10:
        print(f"\n  ✓ Cache is working! ({time2:.1f}ms vs {time1:.1f}ms)")
    else:
        print(f"\n  ⚠ Cache might not be working ({time2:.1f}ms vs {time1:.1f}ms)")

    # Verify results are identical
    if result1 == result2:
        print("  ✓ Results are identical")
    else:
        print("  ✗ Results differ!")

    print("\n" + "=" * 60)
    print("Test Complete")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    asyncio.run(test_fhi_calculator())
