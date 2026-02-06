"""
Pytest configuration and fixtures for ML Service tests.
"""

import pytest
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch


@pytest.fixture
def sample_bounds():
    """Delhi NCR bounds for testing."""
    return (28.4, 76.8, 28.9, 77.4)  # lat_min, lng_min, lat_max, lng_max


@pytest.fixture
def sample_point():
    """Sample point in Delhi (Connaught Place)."""
    return (28.6315, 77.2167)  # lat, lng


@pytest.fixture
def sample_dates():
    """Sample date range for testing."""
    end = datetime.now()
    start = end - timedelta(days=30)
    return start, end


@pytest.fixture
def sample_time_series():
    """Generate sample time series data."""
    np.random.seed(42)
    n_samples = 100

    # Simulate water level with trend and noise
    time = np.arange(n_samples)
    trend = 0.01 * time
    seasonal = 0.5 * np.sin(2 * np.pi * time / 30)  # Monthly seasonality
    noise = 0.1 * np.random.randn(n_samples)

    return trend + seasonal + noise + 2.0  # Base level of 2m


@pytest.fixture
def sample_features():
    """Generate sample feature matrix for model testing."""
    np.random.seed(42)
    n_samples = 100
    n_features = 10

    X = np.random.randn(n_samples, n_features)
    return X


@pytest.fixture
def sample_sequence_features():
    """Generate sample sequence features for LSTM."""
    np.random.seed(42)
    n_samples = 50
    seq_length = 30
    n_features = 10

    X = np.random.randn(n_samples, seq_length, n_features)
    return X


@pytest.fixture
def sample_embeddings():
    """Generate sample AlphaEarth embeddings."""
    np.random.seed(42)
    n_samples = 50
    embedding_dim = 64

    return np.random.randn(n_samples, embedding_dim)


@pytest.fixture
def sample_labels():
    """Generate sample binary flood labels."""
    np.random.seed(42)
    n_samples = 100

    # ~20% flood events
    return (np.random.rand(n_samples) > 0.8).astype(float)


@pytest.fixture
def mock_gee_client():
    """Mock GEE client for testing without actual GEE calls."""
    with patch("src.data.gee_client.gee_client") as mock:
        mock._initialized = True
        mock.initialize = MagicMock()
        mock.bounds_to_geometry = MagicMock(return_value=MagicMock())
        mock.point_to_geometry = MagicMock(return_value=MagicMock())
        mock.point_buffer = MagicMock(return_value=MagicMock())
        yield mock


@pytest.fixture
def mock_ee():
    """Mock Earth Engine module."""
    with patch("ee.Initialize") as mock_init, \
         patch("ee.Image") as mock_image, \
         patch("ee.ImageCollection") as mock_collection, \
         patch("ee.Geometry") as mock_geom:

        # Configure mocks
        mock_init.return_value = None

        # Mock image
        mock_img = MagicMock()
        mock_img.reduceRegion.return_value.getInfo.return_value = {
            "elevation_mean": 220.0,
            "elevation_min": 190.0,
            "elevation_max": 300.0,
            "slope_mean": 2.5,
        }
        mock_image.return_value = mock_img

        # Mock collection
        mock_coll = MagicMock()
        mock_coll.filterDate.return_value = mock_coll
        mock_coll.filterBounds.return_value = mock_coll
        mock_coll.first.return_value = mock_img
        mock_collection.return_value = mock_coll

        yield {
            "init": mock_init,
            "image": mock_image,
            "collection": mock_collection,
            "geometry": mock_geom,
        }
