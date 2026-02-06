"""
Graph Attention Network (GAT) for Urban Waterlogging Hotspot Prediction.

Implements a 2-layer GAT model based on research showing excellent performance
with limited labeled data (94 samples → 0.91 AUC in Dalian study).

Key Features:
- Multi-head attention mechanism learns importance weights for neighbors
- Semi-supervised learning leverages unlabeled nodes via message passing
- Works well with small datasets (<300 samples)
- Automatically learns spatial relationships between hotspots

Architecture (from Dalian paper):
- Layer 1: 4-head attention, input_dim → hidden_dim
- Layer 2: 4-head attention, hidden_dim → 2 (classification)
- Activation: LeakyReLU (alpha=0.2)
- Dropout: 0.5 for regularization

References:
- Dalian study (2023): GAT for flood susceptibility (0.91 AUC with 94 samples)
- Velickovic et al. (2018): Graph Attention Networks (original GAT paper)
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from typing import Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)

# Check if PyTorch Geometric is available
try:
    from torch_geometric.nn import GATConv
    from torch_geometric.data import Data
    from torch_geometric.utils import add_self_loops
    TORCH_GEOMETRIC_AVAILABLE = True
except ImportError:
    TORCH_GEOMETRIC_AVAILABLE = False
    logger.warning("PyTorch Geometric not available. GAT model will not work.")


class HotspotGAT(nn.Module):
    """
    Graph Attention Network for hotspot flood susceptibility prediction.

    Designed for small labeled datasets with semi-supervised learning.
    The model learns to aggregate information from spatial neighbors using
    attention mechanisms.

    Args:
        in_channels: Number of input features (default: 18 for enhanced features)
        hidden_channels: Hidden layer dimension (default: 16)
        heads: Number of attention heads (default: 4)
        dropout: Dropout rate (default: 0.5)
        negative_slope: LeakyReLU negative slope (default: 0.2)
    """

    def __init__(
        self,
        in_channels: int = 18,
        hidden_channels: int = 16,
        heads: int = 4,
        dropout: float = 0.5,
        negative_slope: float = 0.2,
    ):
        super().__init__()

        if not TORCH_GEOMETRIC_AVAILABLE:
            raise ImportError("PyTorch Geometric is required for GAT model")

        self.in_channels = in_channels
        self.hidden_channels = hidden_channels
        self.heads = heads
        self.dropout = dropout
        self.negative_slope = negative_slope

        # First GAT layer: in_channels → hidden_channels * heads
        self.conv1 = GATConv(
            in_channels=in_channels,
            out_channels=hidden_channels,
            heads=heads,
            dropout=dropout,
            negative_slope=negative_slope,
            concat=True,  # Concatenate multi-head outputs
        )

        # Second GAT layer: hidden_channels * heads → 2 (binary classification)
        self.conv2 = GATConv(
            in_channels=hidden_channels * heads,
            out_channels=2,  # flood / no_flood
            heads=1,
            dropout=dropout,
            negative_slope=negative_slope,
            concat=False,  # Average multi-head outputs
        )

        # Batch normalization for training stability
        self.bn1 = nn.BatchNorm1d(hidden_channels * heads)

        self._is_trained = False

    def forward(self, x: torch.Tensor, edge_index: torch.Tensor) -> torch.Tensor:
        """
        Forward pass through the GAT.

        Args:
            x: Node features [num_nodes, in_channels]
            edge_index: Graph connectivity [2, num_edges]

        Returns:
            Log softmax probabilities [num_nodes, 2]
        """
        # First GAT layer
        x = self.conv1(x, edge_index)
        x = self.bn1(x)
        x = F.leaky_relu(x, negative_slope=self.negative_slope)
        x = F.dropout(x, p=self.dropout, training=self.training)

        # Second GAT layer
        x = self.conv2(x, edge_index)

        return F.log_softmax(x, dim=1)

    def predict_proba(self, x: torch.Tensor, edge_index: torch.Tensor) -> np.ndarray:
        """
        Get flood probability predictions.

        Returns:
            Array of shape [num_nodes] with flood probabilities
        """
        self.eval()
        with torch.no_grad():
            log_probs = self.forward(x, edge_index)
            probs = torch.exp(log_probs)
            return probs[:, 1].cpu().numpy()  # Return flood class probability

    @property
    def is_trained(self) -> bool:
        """Check if model has been trained."""
        return self._is_trained


class HotspotGATModel:
    """
    Wrapper class for training and inference with the GAT model.

    Handles:
    - Graph construction from hotspot coordinates
    - Training with semi-supervised learning
    - Prediction with confidence scores
    - Model persistence
    """

    def __init__(
        self,
        in_channels: int = 18,
        hidden_channels: int = 16,
        heads: int = 4,
        k_neighbors: int = 8,
        learning_rate: float = 0.005,
        weight_decay: float = 5e-4,
    ):
        """
        Initialize GAT model wrapper.

        Args:
            in_channels: Number of input features
            hidden_channels: Hidden layer dimension
            heads: Number of attention heads
            k_neighbors: Number of neighbors for graph construction
            learning_rate: Adam learning rate
            weight_decay: L2 regularization
        """
        if not TORCH_GEOMETRIC_AVAILABLE:
            raise ImportError("PyTorch Geometric is required")

        self.in_channels = in_channels
        self.hidden_channels = hidden_channels
        self.heads = heads
        self.k_neighbors = k_neighbors
        self.learning_rate = learning_rate
        self.weight_decay = weight_decay

        self.model = HotspotGAT(
            in_channels=in_channels,
            hidden_channels=hidden_channels,
            heads=heads,
        )
        self.optimizer = None
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)

        self._is_trained = False

    def build_graph(
        self,
        features: np.ndarray,
        coordinates: np.ndarray,
    ) -> Data:
        """
        Construct graph from hotspot features and coordinates.

        Uses k-NN connectivity based on geographic distance.

        Args:
            features: Node features [num_nodes, num_features]
            coordinates: Lat/lng coordinates [num_nodes, 2]

        Returns:
            PyTorch Geometric Data object
        """
        from scipy.spatial import distance_matrix

        num_nodes = len(features)

        # Compute pairwise distances
        dist_matrix = distance_matrix(coordinates, coordinates)

        # Create k-NN edges
        edge_list = []
        for i in range(num_nodes):
            # Get k nearest neighbors (excluding self)
            distances = dist_matrix[i]
            k = min(self.k_neighbors, num_nodes - 1)
            nearest_indices = np.argsort(distances)[1:k+1]  # Exclude self

            for j in nearest_indices:
                edge_list.append([i, j])
                edge_list.append([j, i])  # Undirected graph

        # Remove duplicates
        edge_list = list(set(tuple(e) for e in edge_list))
        edge_index = torch.tensor(edge_list, dtype=torch.long).t().contiguous()

        # Add self-loops
        edge_index, _ = add_self_loops(edge_index, num_nodes=num_nodes)

        # Create data object
        x = torch.tensor(features, dtype=torch.float32)
        data = Data(x=x, edge_index=edge_index)

        return data.to(self.device)

    def train(
        self,
        features: np.ndarray,
        coordinates: np.ndarray,
        labels: np.ndarray,
        train_mask: Optional[np.ndarray] = None,
        epochs: int = 200,
        patience: int = 20,
        verbose: bool = True,
    ) -> Dict[str, List[float]]:
        """
        Train the GAT model.

        Supports semi-supervised learning where only a subset of nodes
        have labels (train_mask specifies labeled nodes).

        Args:
            features: Node features [num_nodes, num_features]
            coordinates: Lat/lng coordinates [num_nodes, 2]
            labels: Node labels (0/1) [num_nodes]
            train_mask: Boolean mask for labeled training nodes
            epochs: Maximum training epochs
            patience: Early stopping patience
            verbose: Print training progress

        Returns:
            Dictionary with training history
        """
        # Build graph
        data = self.build_graph(features, coordinates)
        data.y = torch.tensor(labels, dtype=torch.long).to(self.device)

        # Create train mask if not provided
        if train_mask is None:
            train_mask = np.ones(len(labels), dtype=bool)
        data.train_mask = torch.tensor(train_mask, dtype=torch.bool).to(self.device)

        # Initialize optimizer
        self.optimizer = torch.optim.Adam(
            self.model.parameters(),
            lr=self.learning_rate,
            weight_decay=self.weight_decay,
        )

        # Class weights for imbalanced data
        class_counts = np.bincount(labels[train_mask])
        if len(class_counts) == 2 and class_counts[1] > 0:
            weight = torch.tensor(
                [1.0, class_counts[0] / class_counts[1]],
                dtype=torch.float32,
            ).to(self.device)
        else:
            weight = None

        # Training loop
        history = {"loss": [], "accuracy": []}
        best_loss = float("inf")
        patience_counter = 0

        self.model.train()
        for epoch in range(epochs):
            self.optimizer.zero_grad()

            # Forward pass
            out = self.model(data.x, data.edge_index)

            # Compute loss on labeled nodes only
            loss = F.nll_loss(
                out[data.train_mask],
                data.y[data.train_mask],
                weight=weight,
            )

            # Backward pass
            loss.backward()
            self.optimizer.step()

            # Compute accuracy
            pred = out[data.train_mask].argmax(dim=1)
            correct = (pred == data.y[data.train_mask]).sum().item()
            accuracy = correct / data.train_mask.sum().item()

            history["loss"].append(loss.item())
            history["accuracy"].append(accuracy)

            # Early stopping
            if loss.item() < best_loss:
                best_loss = loss.item()
                patience_counter = 0
            else:
                patience_counter += 1

            if patience_counter >= patience:
                if verbose:
                    logger.info(f"Early stopping at epoch {epoch}")
                break

            if verbose and (epoch + 1) % 20 == 0:
                logger.info(
                    f"Epoch {epoch+1}/{epochs}: "
                    f"Loss={loss.item():.4f}, Acc={accuracy:.4f}"
                )

        self._is_trained = True
        self.model._is_trained = True
        self._data = data  # Store for prediction

        return history

    def predict(
        self,
        features: Optional[np.ndarray] = None,
        coordinates: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """
        Get flood probability predictions.

        If no features/coordinates provided, uses training graph.

        Returns:
            Array of flood probabilities [num_nodes]
        """
        if features is not None and coordinates is not None:
            data = self.build_graph(features, coordinates)
        elif hasattr(self, "_data"):
            data = self._data
        else:
            raise ValueError("No data available for prediction")

        return self.model.predict_proba(data.x, data.edge_index)

    def evaluate(
        self,
        features: np.ndarray,
        coordinates: np.ndarray,
        labels: np.ndarray,
        test_mask: Optional[np.ndarray] = None,
    ) -> Dict[str, float]:
        """
        Evaluate model performance.

        Returns:
            Dictionary with AUC, precision, recall, F1 scores
        """
        from sklearn.metrics import roc_auc_score, precision_score, recall_score, f1_score

        probs = self.predict(features, coordinates)

        if test_mask is None:
            test_mask = np.ones(len(labels), dtype=bool)

        y_true = labels[test_mask]
        y_prob = probs[test_mask]
        y_pred = (y_prob > 0.5).astype(int)

        metrics = {
            "auc": roc_auc_score(y_true, y_prob) if len(np.unique(y_true)) > 1 else 0.0,
            "precision": precision_score(y_true, y_pred, zero_division=0),
            "recall": recall_score(y_true, y_pred, zero_division=0),
            "f1": f1_score(y_true, y_pred, zero_division=0),
        }

        return metrics

    def save(self, path: str) -> None:
        """Save model to disk."""
        torch.save({
            "model_state_dict": self.model.state_dict(),
            "config": {
                "in_channels": self.in_channels,
                "hidden_channels": self.hidden_channels,
                "heads": self.heads,
                "k_neighbors": self.k_neighbors,
            },
            "is_trained": self._is_trained,
        }, path)
        logger.info(f"GAT model saved to {path}")

    def load(self, path: str) -> "HotspotGATModel":
        """Load model from disk."""
        checkpoint = torch.load(path, map_location=self.device)
        config = checkpoint["config"]

        # Reinitialize with saved config
        self.in_channels = config["in_channels"]
        self.hidden_channels = config["hidden_channels"]
        self.heads = config["heads"]
        self.k_neighbors = config["k_neighbors"]

        self.model = HotspotGAT(
            in_channels=self.in_channels,
            hidden_channels=self.hidden_channels,
            heads=self.heads,
        ).to(self.device)

        self.model.load_state_dict(checkpoint["model_state_dict"])
        self._is_trained = checkpoint.get("is_trained", True)
        self.model._is_trained = self._is_trained

        logger.info(f"GAT model loaded from {path}")
        return self

    @property
    def is_trained(self) -> bool:
        """Check if model has been trained."""
        return self._is_trained


def create_gat_model(
    in_channels: int = 18,
    k_neighbors: int = 8,
) -> HotspotGATModel:
    """
    Create a default GAT model for hotspot prediction.

    Args:
        in_channels: Number of input features (18 for enhanced features)
        k_neighbors: Number of spatial neighbors for graph

    Returns:
        Configured HotspotGATModel instance
    """
    return HotspotGATModel(
        in_channels=in_channels,
        hidden_channels=16,
        heads=4,
        k_neighbors=k_neighbors,
        learning_rate=0.005,
        weight_decay=5e-4,
    )
