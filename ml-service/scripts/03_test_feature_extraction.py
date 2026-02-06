"""
Test the complete 79-dimensional feature extraction pipeline.
"""

import sys
sys.path.insert(0, '../')

from src.features.extractor import FeatureExtractor
from datetime import datetime
import numpy as np

def test_feature_extraction():
    """Test extracting the full 79-dim feature vector."""
    print("=" * 60)
    print("Testing Feature Extraction Pipeline")
    print("=" * 60)

    delhi_bounds = (28.4, 76.8, 28.9, 77.4)
    reference_date = datetime(2023, 7, 15)  # Mid-monsoon

    print(f"\nLocation: Delhi NCR")
    print(f"Date: {reference_date.date()}")
    print(f"Bounds: {delhi_bounds}")

    # Initialize extractor
    extractor = FeatureExtractor()

    # Extract features
    print("\nExtracting features...")
    try:
        features = extractor.extract_features(delhi_bounds, reference_date)

        print(f"\n✓ Feature extraction successful!")
        print(f"\nFeature groups:")
        print(f"  AlphaEarth embeddings: {features['embeddings'].shape}")
        print(f"  Terrain features: {features['terrain'].shape}")
        print(f"  Precipitation features: {features['precipitation'].shape}")
        print(f"  Temporal features: {features['temporal'].shape}")
        print(f"  Combined vector: {features['combined'].shape}")

        # Verify dimension
        assert features['combined'].shape[0] == 79, "Expected 79 dimensions!"

        # Show sample values
        print(f"\nSample values:")
        print(f"  AlphaEarth[0:5]: {features['embeddings'][:5]}")
        print(f"  Terrain: {features['terrain']}")
        print(f"  Precipitation: {features['precipitation']}")
        print(f"  Temporal: {features['temporal']}")

        # Get feature names
        feature_names = extractor.get_feature_names()
        print(f"\nFeature breakdown:")
        print(f"  Total features: {len(feature_names)}")

        # Show key features with values
        indices = extractor.get_feature_indices()
        combined = features['combined']

        print(f"\nKey terrain features:")
        terrain_start, terrain_end = indices['terrain']
        terrain_names = feature_names[terrain_start:terrain_end]
        for i, name in enumerate(terrain_names):
            print(f"  {name}: {combined[terrain_start + i]:.2f}")

        print(f"\nKey precipitation features:")
        precip_start, precip_end = indices['precipitation']
        precip_names = feature_names[precip_start:precip_end]
        for i, name in enumerate(precip_names):
            print(f"  {name}: {combined[precip_start + i]:.2f}")

        print("\n" + "=" * 60)
        print("✓ Feature extraction test passed!")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"\n✗ Feature extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_feature_extraction()
    sys.exit(0 if success else 1)
