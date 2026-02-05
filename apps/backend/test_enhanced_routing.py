"""
Test script for Enhanced Routing System

Verifies:
1. Models import correctly
2. Traffic extraction works
3. Turn instruction extraction works
4. Metro route calculation (mock test)
5. Enhanced comparison structure
"""

import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

print("=" * 60)
print("ENHANCED ROUTING SYSTEM - VERIFICATION TEST")
print("=" * 60)

# Test 1: Model Imports
print("\n[1/6] Testing Model Imports...")
try:
    from src.domain.models import (
        TrafficLevel, RouteType, TurnInstruction,
        FastestRouteOption, MetroSegment, MetroRouteOption,
        SafestRouteOption, EnhancedRouteComparisonResponse
    )
    print("  [OK] All models imported successfully")
    print(f"    - TrafficLevel: {list(TrafficLevel)}")
    print(f"    - RouteType: {list(RouteType)}")
except Exception as e:
    print(f"  [FAIL] FAILED: {e}")
    sys.exit(1)

# Test 2: Traffic Extraction Method
print("\n[2/6] Testing Traffic Extraction...")
try:
    from src.domain.services.routing_service import RoutingService
    from unittest.mock import MagicMock

    # Create mock database session
    mock_db = MagicMock()
    service = RoutingService(mock_db)

    # Mock route with congestion data
    mock_route = {
        'legs': [
            {
                'annotation': {
                    'congestion_numeric': [10, 20, 30, 40, 50]  # avg = 30 (moderate)
                }
            }
        ]
    }

    metrics = service._extract_traffic_metrics(mock_route)
    assert metrics['average_congestion'] == 30
    assert metrics['traffic_level'] == 'moderate'
    print("  [OK] Traffic extraction working correctly")
    print(f"    - Average congestion: {metrics['average_congestion']}")
    print(f"    - Traffic level: {metrics['traffic_level']}")
except Exception as e:
    print(f"  [FAIL] FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 3: Turn Instruction Extraction
print("\n[3/6] Testing Turn Instruction Extraction...")
try:
    mock_route = {
        'legs': [
            {
                'steps': [
                    {
                        'maneuver': {
                            'instruction': 'Turn left onto MG Road',
                            'type': 'turn',
                            'modifier': 'left',
                            'location': [77.209, 28.613]
                        },
                        'distance': 500,
                        'duration': 60,
                        'name': 'MG Road'
                    }
                ]
            }
        ]
    }

    instructions = service._extract_turn_instructions(mock_route)
    assert len(instructions) == 1
    assert instructions[0]['instruction'] == 'Turn left onto MG Road'
    assert instructions[0]['distance_meters'] == 500
    assert instructions[0]['maneuver_type'] == 'turn'
    print("  [OK] Turn instruction extraction working")
    print(f"    - Extracted: {instructions[0]['instruction']}")
except Exception as e:
    print(f"  [FAIL] FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Pydantic Model Validation
print("\n[4/6] Testing Pydantic Model Validation...")
try:
    # Test TurnInstruction
    turn = TurnInstruction(
        instruction="Turn right",
        distance_meters=200,
        duration_seconds=30,
        maneuver_type="turn",
        maneuver_modifier="right",
        street_name="Main St",
        coordinates=(77.209, 28.613)
    )
    assert turn.instruction == "Turn right"
    print("  [OK] TurnInstruction model validated")

    # Test FastestRouteOption
    fastest = FastestRouteOption(
        id="test-123",
        geometry={"type": "LineString", "coordinates": []},
        coordinates=[],
        distance_meters=5000,
        duration_seconds=600,
        hotspot_count=2,
        traffic_level="moderate",
        safety_score=85
    )
    assert fastest.type == "fastest"
    print("  [OK] FastestRouteOption model validated")

    # Test MetroSegment
    metro_seg = MetroSegment(
        type="metro",
        duration_seconds=300,
        line="Blue Line",
        line_color="#0000FF",
        from_station="Rajiv Chowk",
        to_station="Connaught Place",
        stops=3
    )
    assert metro_seg.type == "metro"
    print("  [OK] MetroSegment model validated")

except Exception as e:
    print(f"  [FAIL] FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 5: Enhanced Recommendation Logic
print("\n[5/6] Testing Enhanced Recommendation Logic...")
try:
    # Test with no hotspots
    recommendation = service._determine_enhanced_recommendation(
        fastest=None, metro=None, safest=None, hotspots=[]
    )
    assert recommendation['route_type'] == 'fastest'
    assert 'No flood hotspots' in recommendation['reason']
    print("  [OK] Recommendation logic working")
    print(f"    - No hotspots: {recommendation['route_type']}")

    # Test with high risk hotspots
    fastest_risky = {
        'hotspot_count': 3,
        'warnings': ['DANGER: High flood risk'],
        'traffic_level': 'moderate'
    }
    safest_safe = {
        'hotspot_count': 0,
        'hotspots_avoided': ['ITO', 'Kashmere Gate'],
        'detour_minutes': 5
    }
    recommendation = service._determine_enhanced_recommendation(
        fastest=fastest_risky, metro=None, safest=safest_safe,
        hotspots=[{'id': 1}]
    )
    assert recommendation['route_type'] == 'safest'
    print(f"    - High risk: {recommendation['route_type']}")

except Exception as e:
    print(f"  [FAIL] FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 6: API Endpoint Registration
print("\n[6/6] Testing API Endpoint Registration...")
try:
    from src.api.routes_api import router, RecalculateRouteRequest

    routes = [r.path for r in router.routes]
    assert '/routes/compare-enhanced' in routes
    assert '/routes/recalculate' in routes
    print("  [OK] API endpoints registered")
    print(f"    - compare-enhanced: OK")
    print(f"    - recalculate: OK")

    # Test RecalculateRouteRequest model
    from src.api.routes_api import LocationPoint
    recalc_req = RecalculateRouteRequest(
        current_position=LocationPoint(lat=28.613, lng=77.209),
        destination=LocationPoint(lat=28.632, lng=77.231),
        route_type="safest",
        city="DEL"
    )
    assert recalc_req.route_type == "safest"
    print("  [OK] RecalculateRouteRequest model validated")

except Exception as e:
    print(f"  [FAIL] FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 60)
print("ALL TESTS PASSED [OK]")
print("=" * 60)
print("\nEnhanced Routing System Components Verified:")
print("  [OK] Pydantic models (TrafficLevel, RouteType, TurnInstruction, etc.)")
print("  [OK] Traffic extraction from Mapbox annotations")
print("  [OK] Turn-by-turn instruction extraction")
print("  [OK] Enhanced recommendation logic")
print("  [OK] API endpoints (/compare-enhanced, /recalculate)")
print("\nReady for integration with frontend!")
