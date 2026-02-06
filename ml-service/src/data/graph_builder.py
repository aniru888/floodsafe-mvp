"""
Graph construction for spatial flood modeling with GNN.

Builds spatial graphs from grid points to model flood propagation patterns.
"""

from typing import List, Tuple, Dict, Optional
import numpy as np
from scipy.spatial import cKDTree
import logging

try:
    import torch
    from torch_geometric.data import Data
except ImportError:
    torch = None
    Data = None

logger = logging.getLogger(__name__)


class SpatialGraphBuilder:
    """
    Build spatial graphs for flood prediction using GNN.

    Creates graphs where:
    - Nodes: Grid points or sensor locations
    - Edges: Spatial proximity (k-NN) or drainage connectivity
    - Node features: 81-dim feature vectors (AlphaEarth + terrain + precip + temporal + GloFAS)
    - Edge features: Distance, elevation difference
    """

    def __init__(
        self,
        k_neighbors: int = 5,
        max_distance_km: Optional[float] = None,
        include_edge_features: bool = True,
    ):
        """
        Initialize graph builder.

        Args:
            k_neighbors: Number of nearest neighbors to connect
            max_distance_km: Maximum distance for edges (None = no limit)
            include_edge_features: Whether to compute edge features
        """
        self.k_neighbors = k_neighbors
        self.max_distance_km = max_distance_km
        self.include_edge_features = include_edge_features

        if torch is None:
            raise ImportError(
                "PyTorch and torch-geometric are required for GNN. "
                "Install: pip install torch torch-geometric"
            )

    def build_knn_graph(
        self,
        coordinates: np.ndarray,
        features: np.ndarray,
        labels: Optional[np.ndarray] = None,
        elevations: Optional[np.ndarray] = None,
    ) -> Data:
        """
        Build k-NN graph from spatial coordinates.

        Args:
            coordinates: (N, 2) array of (lat, lng) coordinates
            features: (N, feature_dim) array of node features
            labels: Optional (N,) array of flood labels (0/1)
            elevations: Optional (N,) array of elevations for edge features

        Returns:
            torch_geometric.data.Data object with:
            - x: Node features (N, feature_dim)
            - edge_index: Edge connectivity (2, E)
            - edge_attr: Edge features (E, edge_feature_dim) [optional]
            - y: Node labels (N,) [optional]
            - pos: Node positions (N, 2)
        """
        N = len(coordinates)

        if N < self.k_neighbors:
            logger.warning(
                f"Only {N} nodes, reducing k_neighbors from {self.k_neighbors} to {N-1}"
            )
            k = max(1, N - 1)
        else:
            k = self.k_neighbors

        # Build k-NN graph using KDTree
        tree = cKDTree(coordinates)

        # Query k+1 neighbors (includes self)
        distances, indices = tree.query(coordinates, k=k + 1)

        # Remove self-connections
        distances = distances[:, 1:]  # (N, k)
        indices = indices[:, 1:]  # (N, k)

        # Build edge list
        edge_index_list = []
        edge_distances = []

        for i in range(N):
            for j_idx, j in enumerate(indices[i]):
                dist_km = self._haversine_distance(
                    coordinates[i, 0], coordinates[i, 1],
                    coordinates[j, 0], coordinates[j, 1]
                )

                # Filter by max distance if specified
                if self.max_distance_km is not None and dist_km > self.max_distance_km:
                    continue

                edge_index_list.append([i, j])
                edge_distances.append(dist_km)

        if len(edge_index_list) == 0:
            logger.warning("No edges within distance threshold, using all k-NN edges")
            # Fallback: use all k-NN edges
            for i in range(N):
                for j in indices[i]:
                    dist_km = self._haversine_distance(
                        coordinates[i, 0], coordinates[i, 1],
                        coordinates[j, 0], coordinates[j, 1]
                    )
                    edge_index_list.append([i, j])
                    edge_distances.append(dist_km)

        # Convert to tensors
        edge_index = torch.tensor(edge_index_list, dtype=torch.long).t()  # (2, E)
        x = torch.tensor(features, dtype=torch.float)  # (N, feature_dim)
        pos = torch.tensor(coordinates, dtype=torch.float)  # (N, 2)

        # Build Data object
        data_dict = {
            'x': x,
            'edge_index': edge_index,
            'pos': pos,
        }

        # Add edge features if requested
        if self.include_edge_features:
            edge_attr = self._compute_edge_features(
                edge_index,
                coordinates,
                edge_distances,
                elevations
            )
            data_dict['edge_attr'] = edge_attr

        # Add labels if provided
        if labels is not None:
            data_dict['y'] = torch.tensor(labels, dtype=torch.float)

        data = Data(**data_dict)

        logger.info(
            f"Built k-NN graph: {N} nodes, {edge_index.shape[1]} edges "
            f"(k={self.k_neighbors})"
        )

        return data

    def build_grid_graph(
        self,
        lat_min: float,
        lat_max: float,
        lng_min: float,
        lng_max: float,
        resolution_km: float = 2.0,
        features: Optional[np.ndarray] = None,
    ) -> Tuple[np.ndarray, Data]:
        """
        Build graph from regular grid.

        Args:
            lat_min, lat_max, lng_min, lng_max: Grid bounds
            resolution_km: Grid cell size in km
            features: Optional (N, feature_dim) features for grid points

        Returns:
            (coordinates, graph_data) tuple
        """
        # Generate grid points
        # Approximate: 1 degree lat ≈ 111 km
        lat_step = resolution_km / 111.0
        lng_step = resolution_km / (111.0 * np.cos(np.radians((lat_min + lat_max) / 2)))

        lats = np.arange(lat_min, lat_max, lat_step)
        lngs = np.arange(lng_min, lng_max, lng_step)

        lat_grid, lng_grid = np.meshgrid(lats, lngs, indexing='ij')
        coordinates = np.stack([lat_grid.ravel(), lng_grid.ravel()], axis=1)

        N = len(coordinates)
        logger.info(f"Generated grid: {len(lats)}×{len(lngs)} = {N} points")

        # Use dummy features if not provided
        if features is None:
            features = np.random.randn(N, 81)  # 81-dim feature vector
            logger.warning("No features provided, using random features for graph structure")

        # Build k-NN graph
        graph = self.build_knn_graph(coordinates, features)

        return coordinates, graph

    def _compute_edge_features(
        self,
        edge_index: torch.Tensor,
        coordinates: np.ndarray,
        distances: List[float],
        elevations: Optional[np.ndarray] = None,
    ) -> torch.Tensor:
        """
        Compute edge features.

        Features:
        - Distance between nodes (normalized)
        - Elevation difference (if available)
        - Direction (cos/sin of bearing)

        Returns:
            (E, edge_feature_dim) tensor
        """
        E = edge_index.shape[1]
        edge_features = []

        # Distance feature (normalized by max)
        distances_array = np.array(distances)
        max_dist = distances_array.max() if len(distances_array) > 0 else 1.0
        dist_norm = distances_array / max_dist
        edge_features.append(dist_norm.reshape(-1, 1))

        # Elevation difference (if available)
        if elevations is not None:
            src_indices = edge_index[0].numpy()
            dst_indices = edge_index[1].numpy()
            elev_diff = elevations[dst_indices] - elevations[src_indices]
            # Normalize by std dev
            elev_diff_norm = elev_diff / (np.std(elev_diff) + 1e-6)
            edge_features.append(elev_diff_norm.reshape(-1, 1))

        # Direction features (bearing)
        src_indices = edge_index[0].numpy()
        dst_indices = edge_index[1].numpy()

        src_coords = coordinates[src_indices]
        dst_coords = coordinates[dst_indices]

        # Compute bearing (simplified, not true great circle)
        dlng = dst_coords[:, 1] - src_coords[:, 1]
        dlat = dst_coords[:, 0] - src_coords[:, 0]
        bearing = np.arctan2(dlng, dlat)

        # Convert to cos/sin (circular features)
        edge_features.append(np.cos(bearing).reshape(-1, 1))
        edge_features.append(np.sin(bearing).reshape(-1, 1))

        # Concatenate all features
        edge_attr = np.concatenate(edge_features, axis=1)

        return torch.tensor(edge_attr, dtype=torch.float)

    def _haversine_distance(
        self,
        lat1: float,
        lng1: float,
        lat2: float,
        lng2: float
    ) -> float:
        """
        Calculate great-circle distance in km using Haversine formula.

        Args:
            lat1, lng1: First point
            lat2, lng2: Second point

        Returns:
            Distance in kilometers
        """
        R = 6371.0  # Earth radius in km

        lat1_rad = np.radians(lat1)
        lat2_rad = np.radians(lat2)
        dlat = np.radians(lat2 - lat1)
        dlng = np.radians(lng2 - lng1)

        a = (
            np.sin(dlat / 2) ** 2 +
            np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlng / 2) ** 2
        )
        c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))

        return R * c

    def add_temporal_edges(
        self,
        graph: Data,
        num_timesteps: int,
        temporal_k: int = 3,
    ) -> Data:
        """
        Add temporal edges for spatio-temporal graph.

        Connects nodes across time: node_t → node_{t+1}, node_{t+2}, ...

        Args:
            graph: Spatial graph (N nodes)
            num_timesteps: Number of time steps (T)
            temporal_k: Number of future timesteps to connect

        Returns:
            Spatio-temporal graph with N*T nodes
        """
        N = graph.x.shape[0]
        T = num_timesteps

        # Replicate spatial graph for each timestep
        x_list = [graph.x for _ in range(T)]
        edge_index_list = []

        # Add spatial edges for each timestep
        for t in range(T):
            # Offset node indices for this timestep
            spatial_edges = graph.edge_index + (t * N)
            edge_index_list.append(spatial_edges)

        # Add temporal edges
        for t in range(T - 1):
            for k in range(1, min(temporal_k + 1, T - t)):
                # Connect node i at time t to node i at time t+k
                src = torch.arange(N) + (t * N)
                dst = torch.arange(N) + ((t + k) * N)
                temporal_edges = torch.stack([src, dst], dim=0)
                edge_index_list.append(temporal_edges)

        # Concatenate all
        x_temporal = torch.cat(x_list, dim=0)  # (N*T, feature_dim)
        edge_index_temporal = torch.cat(edge_index_list, dim=1)  # (2, E_total)

        # Create new Data object
        data_temporal = Data(
            x=x_temporal,
            edge_index=edge_index_temporal,
        )

        if hasattr(graph, 'y'):
            y_list = [graph.y for _ in range(T)]
            data_temporal.y = torch.cat(y_list, dim=0)

        logger.info(
            f"Built spatio-temporal graph: {N*T} nodes ({N}×{T}), "
            f"{edge_index_temporal.shape[1]} edges"
        )

        return data_temporal

    def __repr__(self) -> str:
        return (
            f"SpatialGraphBuilder(k={self.k_neighbors}, "
            f"max_dist={self.max_distance_km}km, "
            f"edge_features={self.include_edge_features})"
        )
