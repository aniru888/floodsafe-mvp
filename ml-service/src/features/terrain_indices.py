"""
Terrain Indices Calculator for Flood Susceptibility Mapping.

Computes research-validated terrain indices from DEM data via Google Earth Engine:
- TPI (Topographic Position Index): Relative elevation position
- TRI (Terrain Ruggedness Index): Local surface roughness
- TWI (Topographic Wetness Index): Flow accumulation tendency
- SPI (Stream Power Index): Erosive power of flowing water

References:
- Malda Flood Study (2024): Added TPI, TRI, TWI, SPI for improved accuracy
- Mumbai FSM Study (2025): SHAP shows terrain indices as top predictors
- Wilson & Gallant (2000): TWI/SPI formulations
"""

import ee
import numpy as np
from typing import Dict, Tuple, Optional
import logging

from ..data.gee_client import gee_client
from ..core.config import settings

logger = logging.getLogger(__name__)


class TerrainIndicesCalculator:
    """
    Calculate terrain indices from DEM for flood susceptibility.

    All indices are derived from SRTM 30m DEM via Google Earth Engine.
    Uses neighborhood operations for local statistics.
    """

    # Kernel sizes for neighborhood analysis
    TPI_KERNEL_RADIUS = 3  # 7x7 window (radius 3 pixels = 210m at 30m resolution)
    TRI_KERNEL_RADIUS = 1  # 3x3 window (standard TRI)

    def __init__(self):
        """Initialize terrain indices calculator."""
        self._dem = None
        self._terrain = None
        self._initialized = False

    def _initialize(self) -> None:
        """Initialize GEE and load DEM."""
        if self._initialized:
            return

        gee_client.initialize()
        self._dem = ee.Image(settings.GEE_DEM)
        self._terrain = ee.Terrain.products(self._dem)
        self._initialized = True
        logger.info("TerrainIndicesCalculator initialized")

    def get_terrain_indices(
        self,
        bounds: Tuple[float, float, float, float],
        scale: int = 30,
    ) -> Dict[str, float]:
        """
        Calculate all terrain indices for a region.

        Args:
            bounds: (lat_min, lng_min, lat_max, lng_max)
            scale: Resolution in meters (default: 30m)

        Returns:
            Dictionary with terrain indices:
            - tpi: Topographic Position Index (meters)
            - tri: Terrain Ruggedness Index (meters)
            - twi: Topographic Wetness Index (dimensionless)
            - spi: Stream Power Index (dimensionless)
        """
        self._initialize()

        geometry = gee_client.bounds_to_geometry(bounds)

        # Calculate all indices
        tpi = self._calculate_tpi(geometry, scale)
        tri = self._calculate_tri(geometry, scale)
        twi = self._calculate_twi(geometry, scale)
        spi = self._calculate_spi(geometry, scale)

        return {
            "tpi": tpi,
            "tri": tri,
            "twi": twi,
            "spi": spi,
        }

    def get_terrain_indices_at_point(
        self,
        lat: float,
        lng: float,
        buffer_km: float = 0.5,
    ) -> Dict[str, float]:
        """
        Calculate terrain indices for a point location.

        Args:
            lat: Latitude
            lng: Longitude
            buffer_km: Buffer radius in km

        Returns:
            Dictionary with terrain indices
        """
        # Convert point to bounds
        buffer_deg = buffer_km / 111.0
        bounds = (
            lat - buffer_deg,
            lng - buffer_deg,
            lat + buffer_deg,
            lng + buffer_deg,
        )

        return self.get_terrain_indices(bounds)

    def _calculate_tpi(self, geometry: ee.Geometry, scale: int) -> float:
        """
        Calculate Topographic Position Index (TPI).

        TPI = elevation - mean(elevation in neighborhood)

        Interpretation:
        - TPI > 0: Location is higher than surroundings (ridge, hilltop)
        - TPI < 0: Location is lower than surroundings (valley, depression)
        - TPI ~ 0: Location is at similar elevation to surroundings (flat, slope)

        Negative TPI indicates flood-prone low-lying areas.
        """
        try:
            # Create neighborhood kernel
            kernel = ee.Kernel.circle(
                radius=self.TPI_KERNEL_RADIUS,
                units="pixels"
            )

            # Calculate neighborhood mean
            local_mean = self._dem.reduceNeighborhood(
                reducer=ee.Reducer.mean(),
                kernel=kernel
            )

            # TPI = elevation - local mean
            tpi = self._dem.subtract(local_mean)

            # Reduce to region mean
            result = tpi.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=geometry,
                scale=scale,
                maxPixels=1e8,
            ).getInfo()

            tpi_value = result.get("elevation", 0.0)
            return float(tpi_value) if tpi_value is not None else 0.0

        except Exception as e:
            logger.warning(f"TPI calculation failed: {e}")
            return 0.0

    def _calculate_tri(self, geometry: ee.Geometry, scale: int) -> float:
        """
        Calculate Terrain Ruggedness Index (TRI).

        TRI = std(elevation in 3x3 neighborhood)

        Alternatively defined as mean absolute difference from center cell.
        Higher TRI indicates rougher terrain; lower TRI indicates flat areas.

        For flood susceptibility, low TRI may indicate areas where water pools.
        """
        try:
            # Create 3x3 kernel
            kernel = ee.Kernel.square(
                radius=self.TRI_KERNEL_RADIUS,
                units="pixels"
            )

            # Calculate neighborhood standard deviation
            tri = self._dem.reduceNeighborhood(
                reducer=ee.Reducer.stdDev(),
                kernel=kernel
            )

            # Reduce to region mean
            result = tri.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=geometry,
                scale=scale,
                maxPixels=1e8,
            ).getInfo()

            # Band name after stdDev is 'elevation_stdDev'
            tri_value = result.get("elevation_stdDev", result.get("elevation", 0.0))
            return float(tri_value) if tri_value is not None else 0.0

        except Exception as e:
            logger.warning(f"TRI calculation failed: {e}")
            return 0.0

    def _calculate_twi(self, geometry: ee.Geometry, scale: int) -> float:
        """
        Calculate Topographic Wetness Index (TWI).

        TWI = ln(specific_catchment_area / tan(slope))
            = ln(flow_accumulation * cell_size / tan(slope_radians))

        Higher TWI indicates areas that accumulate water:
        - Flat areas with large upslope contributing area
        - Valley bottoms and channels
        - Areas prone to saturation

        This is a critical predictor for flood susceptibility.

        Note: GEE doesn't have built-in flow accumulation, so we use
        a simplified proxy based on local curvature and slope.
        """
        try:
            # Get slope in degrees
            slope_deg = self._terrain.select("slope")

            # Convert to radians and calculate tangent
            slope_rad = slope_deg.multiply(np.pi / 180.0)

            # Avoid division by zero - minimum slope of 0.1 degrees
            tan_slope = slope_rad.tan().max(0.001745)  # tan(0.1 deg)

            # Simplified TWI using a proxy for flow accumulation
            # In GEE, we can approximate using inverse of local prominence
            # Higher values where: low slope + surrounded by higher terrain

            # Calculate local curvature (proxy for flow accumulation tendency)
            kernel = ee.Kernel.circle(radius=5, units="pixels")
            local_max = self._dem.reduceNeighborhood(
                reducer=ee.Reducer.max(),
                kernel=kernel
            )
            local_min = self._dem.reduceNeighborhood(
                reducer=ee.Reducer.min(),
                kernel=kernel
            )

            # Local relief (range)
            relief = local_max.subtract(local_min).add(1)  # Add 1 to avoid log(0)

            # Proxy for contributing area: inverse of position in relief
            # (lower positions have more contributing area)
            position = self._dem.subtract(local_min).add(1)
            contributing_area_proxy = relief.divide(position)

            # TWI = ln(contributing_area / tan_slope)
            twi = contributing_area_proxy.divide(tan_slope).log().rename("twi")

            # Reduce to region mean
            result = twi.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=geometry,
                scale=scale,
                maxPixels=1e8,
            ).getInfo()

            # Get TWI value (band renamed to 'twi')
            twi_value = result.get("twi")
            if twi_value is None:
                # Try other possible band names from the computation chain
                for key in result.keys():
                    if result[key] is not None:
                        twi_value = result[key]
                        break
            return float(twi_value) if twi_value is not None else 5.0  # Default typical TWI

        except Exception as e:
            logger.warning(f"TWI calculation failed: {e}")
            return 5.0  # Default value

    def _calculate_spi(self, geometry: ee.Geometry, scale: int) -> float:
        """
        Calculate Stream Power Index (SPI).

        SPI = specific_catchment_area * tan(slope)
            = flow_accumulation * cell_size * tan(slope_radians)

        Higher SPI indicates greater erosive power:
        - Areas with steep slopes and large upslope area
        - Stream channels
        - Areas with high runoff energy

        For flood susceptibility, high SPI can indicate flash flood risk.
        """
        try:
            # Get slope in degrees
            slope_deg = self._terrain.select("slope")

            # Convert to radians and calculate tangent
            slope_rad = slope_deg.multiply(np.pi / 180.0)
            tan_slope = slope_rad.tan()

            # Similar to TWI, use proxy for contributing area
            kernel = ee.Kernel.circle(radius=5, units="pixels")
            local_max = self._dem.reduceNeighborhood(
                reducer=ee.Reducer.max(),
                kernel=kernel
            )
            local_min = self._dem.reduceNeighborhood(
                reducer=ee.Reducer.min(),
                kernel=kernel
            )

            relief = local_max.subtract(local_min).add(1)
            position = self._dem.subtract(local_min).add(1)
            contributing_area_proxy = relief.divide(position)

            # SPI = contributing_area * tan_slope
            spi = contributing_area_proxy.multiply(tan_slope).rename("spi")

            # Reduce to region mean
            result = spi.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=geometry,
                scale=scale,
                maxPixels=1e8,
            ).getInfo()

            # Get SPI value (band renamed to 'spi')
            spi_value = result.get("spi")
            if spi_value is None:
                # Try other possible band names from the computation chain
                for key in result.keys():
                    if result[key] is not None:
                        spi_value = result[key]
                        break
            return float(spi_value) if spi_value is not None else 0.1  # Default

        except Exception as e:
            logger.warning(f"SPI calculation failed: {e}")
            return 0.1  # Default value


# Singleton instance
terrain_indices_calculator = TerrainIndicesCalculator()


def get_terrain_indices_at_point(
    lat: float,
    lng: float,
    buffer_km: float = 0.5,
) -> Dict[str, float]:
    """
    Convenience function to get terrain indices at a point.

    Args:
        lat: Latitude
        lng: Longitude
        buffer_km: Buffer radius in km

    Returns:
        Dictionary with TPI, TRI, TWI, SPI values
    """
    return terrain_indices_calculator.get_terrain_indices_at_point(lat, lng, buffer_km)
