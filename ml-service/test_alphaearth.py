"""
Quick test script to verify AlphaEarth fetcher implementation.
Run with: python test_alphaearth.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Test imports
try:
    from data.alphaearth import AlphaEarthFetcher, alphaearth_fetcher
    from data.base import DataFetchError
    from core.config import settings, ALPHAEARTH_BANDS
    print("✓ All imports successful")
except ImportError as e:
    print(f"✗ Import error: {e}")
    sys.exit(1)

# Test instantiation
try:
    fetcher = AlphaEarthFetcher()
    print(f"✓ AlphaEarthFetcher instantiated")
    print(f"  - Source name: {fetcher.source_name}")
    print(f"  - Cache TTL: {fetcher.cache_ttl_days} days")
except Exception as e:
    print(f"✗ Instantiation error: {e}")
    sys.exit(1)

# Test properties
assert fetcher.source_name == "alphaearth", "Source name mismatch"
assert fetcher.cache_ttl_days == settings.CACHE_TTL_ALPHAEARTH, "Cache TTL mismatch"
print("✓ Properties validated")

# Test singleton instance
assert isinstance(alphaearth_fetcher, AlphaEarthFetcher), "Singleton instance type mismatch"
print("✓ Singleton instance available")

# Test ALPHAEARTH_BANDS
assert len(ALPHAEARTH_BANDS) == 64, f"Expected 64 bands, got {len(ALPHAEARTH_BANDS)}"
assert ALPHAEARTH_BANDS[0] == "A00", "First band should be A00"
assert ALPHAEARTH_BANDS[-1] == "A63", "Last band should be A63"
print(f"✓ AlphaEarth bands configured correctly (64 bands: A00-A63)")

# Test method signatures
import inspect

# Check get_embedding_at_point
sig = inspect.signature(fetcher.get_embedding_at_point)
params = list(sig.parameters.keys())
assert "lat" in params, "get_embedding_at_point missing 'lat' parameter"
assert "lng" in params, "get_embedding_at_point missing 'lng' parameter"
assert "year" in params, "get_embedding_at_point missing 'year' parameter"
print("✓ get_embedding_at_point signature correct")

# Check get_aggregated_embedding
sig = inspect.signature(fetcher.get_aggregated_embedding)
params = list(sig.parameters.keys())
assert "bounds" in params, "get_aggregated_embedding missing 'bounds' parameter"
assert "year" in params, "get_aggregated_embedding missing 'year' parameter"
assert "method" in params, "get_aggregated_embedding missing 'method' parameter"
print("✓ get_aggregated_embedding signature correct")

# Check get_region_embeddings
sig = inspect.signature(fetcher.get_region_embeddings)
params = list(sig.parameters.keys())
assert "bounds" in params, "get_region_embeddings missing 'bounds' parameter"
assert "year" in params, "get_region_embeddings missing 'year' parameter"
assert "scale" in params, "get_region_embeddings missing 'scale' parameter"
print("✓ get_region_embeddings signature correct")

print("\n" + "="*60)
print("SUCCESS: All tests passed!")
print("="*60)
print("\nAlphaEarth fetcher is ready to use.")
print("\nExample usage:")
print("""
from data.alphaearth import alphaearth_fetcher

# Get embedding at Delhi center
embedding = alphaearth_fetcher.get_embedding_at_point(28.6139, 77.2090)
print(f"Embedding shape: {embedding.shape}")  # (64,)

# Get aggregated embedding for Delhi NCR
bounds = (28.4, 76.8, 28.9, 77.4)
avg_embedding = alphaearth_fetcher.get_aggregated_embedding(bounds)
print(f"Average embedding: {avg_embedding.shape}")  # (64,)

# Get spatial embeddings as a grid
embeddings = alphaearth_fetcher.get_region_embeddings(bounds, scale=100)
print(f"Region embeddings: {embeddings.shape}")  # (H, W, 64)
""")
print("\nNote: GEE authentication required for actual data fetching.")
print("Run: ee.Authenticate() and ee.Initialize(project='gen-lang-client-0669818939')")
