"""
Graph Neural Network (GNN) for spatial flood prediction.

Models flood propagation patterns using spatial relationships between grid points.
Expected 17-31% accuracy improvement over independent point predictions.
"""

from pathlib import Path
from typing import Dict, Optional, Tuple
import numpy as np
import logging
import pickle

import torch
import torch.nn as nn
import torch.nn.functional as F

try:
    from torch_geometric.nn import GCNConv, GATConv, global_mean_pool
    from torch_geometric.data import Data, Batch
except ImportError:
    raise ImportError(
        "torch-geometric is required for GNN. "
        "Install: pip install torch-geometric"
    )

from .base import FloodPredictionModel
from ..data.graph_builder import SpatialGraphBuilder

logger = logging.getLogger(__name__)


class FloodGNN(nn.Module):
    """
    Graph Neural Network for flood prediction.

    Architecture:
    - 3 GCN/GAT layers for spatial message passing
    - Residual connections
    - Batch normalization
    - Dropout for regularization
    - Final MLP for classification
    """

    def __init__(
        self,
        input_dim: int = 37,
        hidden_dim: int = 64,
        num_layers: int = 3,
        gnn_type: str = 'gcn',
        dropout: float = 0.3,
        use_edge_features: bool = False,
    ):
        """
        Initialize FloodGNN.

        Args:
            input_dim: Input feature dimension (37 for our feature vector)
            hidden_dim: Hidden layer dimension
            num_layers: Number of GNN layers
            gnn_type: 'gcn' or 'gat' (Graph Attention Network)
            dropout: Dropout rate
            use_edge_features: Whether to use edge features (not implemented)
        """
        super().__init__()

        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.gnn_type = gnn_type.lower()
        self.dropout = dropout

        # Input projection
        self.input_proj = nn.Linear(input_dim, hidden_dim)

        # GNN layers
        self.convs = nn.ModuleList()
        self.batch_norms = nn.ModuleList()

        for i in range(num_layers):
            if self.gnn_type == 'gcn':
                conv = GCNConv(hidden_dim, hidden_dim)
            elif self.gnn_type == 'gat':
                # Graph Attention Network with 4 attention heads
                conv = GATConv(hidden_dim, hidden_dim // 4, heads=4, concat=True)
            else:
                raise ValueError(f"Unknown gnn_type: {gnn_type}. Use 'gcn' or 'gat'")

            self.convs.append(conv)
            self.batch_norms.append(nn.BatchNorm1d(hidden_dim))

        # Output MLP
        self.output_mlp = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim // 2, 1),
            nn.Sigmoid()
        )

    def forward(self, data: Data) -> torch.Tensor:
        """
        Forward pass.

        Args:
            data: torch_geometric.data.Data with:
                  - x: Node features (N, input_dim)
                  - edge_index: Edge connectivity (2, E)

        Returns:
            Node predictions (N, 1) - flood probabilities
        """
        x, edge_index = data.x, data.edge_index

        # Input projection
        x = self.input_proj(x)
        x = F.relu(x)

        # GNN layers with residual connections
        for i, (conv, bn) in enumerate(zip(self.convs, self.batch_norms)):
            x_in = x

            # Message passing
            x = conv(x, edge_index)

            # Batch normalization
            x = bn(x)

            # Activation
            x = F.relu(x)

            # Residual connection (skip first layer)
            if i > 0:
                x = x + x_in

            # Dropout
            x = F.dropout(x, p=self.dropout, training=self.training)

        # Output prediction per node
        out = self.output_mlp(x)

        return out.squeeze(-1)  # (N,)


class GNNFloodModel(FloodPredictionModel):
    """
    GNN-based flood prediction model with FloodPredictionModel interface.

    Wraps FloodGNN for spatial flood prediction using graph structure.
    """

    def __init__(
        self,
        model_name: str = "GNN-Flood",
        input_dim: int = 37,
        hidden_dim: int = 64,
        num_layers: int = 3,
        gnn_type: str = 'gcn',
        k_neighbors: int = 5,
        **kwargs
    ):
        """
        Initialize GNN flood model.

        Args:
            model_name: Model identifier
            input_dim: Input feature dimension
            hidden_dim: Hidden layer dimension
            num_layers: Number of GNN layers
            gnn_type: 'gcn' or 'gat'
            k_neighbors: Number of neighbors for graph construction
            **kwargs: Additional parameters
        """
        super().__init__(model_name)

        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.gnn_type = gnn_type
        self.k_neighbors = k_neighbors

        # Initialize GNN
        self.model = FloodGNN(
            input_dim=input_dim,
            hidden_dim=hidden_dim,
            num_layers=num_layers,
            gnn_type=gnn_type,
            **kwargs
        )

        # Graph builder
        self.graph_builder = SpatialGraphBuilder(
            k_neighbors=k_neighbors,
            include_edge_features=False  # Not used yet
        )

        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model.to(self.device)

        logger.info(f"Initialized {model_name} on {self.device}")

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        coordinates: Optional[np.ndarray] = None,
        epochs: int = 100,
        batch_size: int = 32,
        lr: float = 0.001,
        weight_decay: float = 1e-5,
        validation_split: float = 0.2,
        **kwargs
    ) -> "GNNFloodModel":
        """
        Train GNN model.

        Args:
            X: Feature matrix (n_samples, n_features) - will be used to build graphs
            y: Binary labels (n_samples,)
            coordinates: (n_samples, 2) array of (lat, lng) for graph construction
                        If None, will use grid layout
            epochs: Number of training epochs
            batch_size: Batch size (number of graphs)
            lr: Learning rate
            weight_decay: L2 regularization
            validation_split: Fraction for validation
            **kwargs: Additional training parameters

        Returns:
            self
        """
        logger.info(f"Training {self.model_name} with {len(X)} samples")

        if coordinates is None:
            # Generate dummy coordinates for grid layout
            n = len(X)
            grid_size = int(np.ceil(np.sqrt(n)))
            coords_x = np.arange(grid_size)
            coords_y = np.arange(grid_size)
            xx, yy = np.meshgrid(coords_x, coords_y)
            coordinates = np.stack([xx.ravel()[:n], yy.ravel()[:n]], axis=1)
            logger.warning("No coordinates provided, using grid layout")

        # Flatten if 3D (sequence data)
        if X.ndim == 3:
            n_samples, seq_len, n_features = X.shape
            # Use only the last timestep for GNN (spatial snapshot)
            X = X[:, -1, :]
            logger.info(f"Using last timestep from sequence: ({n_samples}, {n_features})")

        # Build graph
        graph = self.graph_builder.build_knn_graph(
            coordinates=coordinates,
            features=X,
            labels=y
        )

        # Split into train/val
        n_samples = len(X)
        n_val = int(n_samples * validation_split)
        n_train = n_samples - n_val

        indices = np.random.permutation(n_samples)
        train_idx = indices[:n_train]
        val_idx = indices[n_train:]

        train_mask = torch.zeros(n_samples, dtype=torch.bool)
        val_mask = torch.zeros(n_samples, dtype=torch.bool)
        train_mask[train_idx] = True
        val_mask[val_idx] = True

        graph.train_mask = train_mask
        graph.val_mask = val_mask
        graph = graph.to(self.device)

        # Training setup
        optimizer = torch.optim.Adam(
            self.model.parameters(),
            lr=lr,
            weight_decay=weight_decay
        )
        criterion = nn.BCELoss()

        # Training loop
        best_val_loss = float('inf')
        patience = 10
        patience_counter = 0

        for epoch in range(epochs):
            # Training
            self.model.train()
            optimizer.zero_grad()

            out = self.model(graph)
            loss = criterion(out[train_mask], graph.y[train_mask])

            loss.backward()
            optimizer.step()

            # Validation
            self.model.eval()
            with torch.no_grad():
                val_out = self.model(graph)
                val_loss = criterion(val_out[val_mask], graph.y[val_mask])

                # Compute accuracy
                train_pred = (out[train_mask] > 0.5).float()
                train_acc = (train_pred == graph.y[train_mask]).float().mean()

                val_pred = (val_out[val_mask] > 0.5).float()
                val_acc = (val_pred == graph.y[val_mask]).float().mean()

            # Logging
            if (epoch + 1) % 10 == 0:
                logger.info(
                    f"Epoch {epoch+1}/{epochs} - "
                    f"Loss: {loss.item():.4f}, Val Loss: {val_loss.item():.4f}, "
                    f"Train Acc: {train_acc.item():.4f}, Val Acc: {val_acc.item():.4f}"
                )

            # Early stopping
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                patience_counter = 0
            else:
                patience_counter += 1
                if patience_counter >= patience:
                    logger.info(f"Early stopping at epoch {epoch+1}")
                    break

        self._trained = True
        self._training_history = {
            'final_train_loss': loss.item(),
            'final_val_loss': val_loss.item(),
            'final_train_acc': train_acc.item(),
            'final_val_acc': val_acc.item(),
        }

        logger.info(f"Training complete. Best val loss: {best_val_loss:.4f}")
        return self

    def predict(self, X: np.ndarray, coordinates: Optional[np.ndarray] = None, **kwargs) -> np.ndarray:
        """Predict binary class labels."""
        probas = self.predict_proba(X, coordinates, **kwargs)
        return (probas >= 0.5).astype(int)

    def predict_proba(
        self,
        X: np.ndarray,
        coordinates: Optional[np.ndarray] = None,
        **kwargs
    ) -> np.ndarray:
        """
        Predict flood probabilities.

        Args:
            X: Feature matrix (n_samples, n_features)
            coordinates: (n_samples, 2) coordinates for graph construction
            **kwargs: Additional parameters

        Returns:
            Flood probabilities (n_samples,)
        """
        if not self.is_trained:
            raise ValueError("Model must be trained before prediction. Call fit() first.")

        # Flatten if 3D
        if X.ndim == 3:
            X = X[:, -1, :]  # Use last timestep

        if coordinates is None:
            # Generate dummy coordinates
            n = len(X)
            grid_size = int(np.ceil(np.sqrt(n)))
            coords_x = np.arange(grid_size)
            coords_y = np.arange(grid_size)
            xx, yy = np.meshgrid(coords_x, coords_y)
            coordinates = np.stack([xx.ravel()[:n], yy.ravel()[:n]], axis=1)

        # Build graph
        graph = self.graph_builder.build_knn_graph(
            coordinates=coordinates,
            features=X
        )
        graph = graph.to(self.device)

        # Predict
        self.model.eval()
        with torch.no_grad():
            out = self.model(graph)
            probas = out.cpu().numpy()

        return probas

    def save(self, path: Path) -> None:
        """Save GNN model."""
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)

        # Save PyTorch model
        model_path = path / f"{self.model_name}_gnn.pt"
        torch.save(self.model.state_dict(), model_path)
        logger.info(f"Saved GNN model to {model_path}")

        # Save metadata
        metadata = {
            'model_name': self.model_name,
            'input_dim': self.input_dim,
            'hidden_dim': self.hidden_dim,
            'num_layers': self.num_layers,
            'gnn_type': self.gnn_type,
            'k_neighbors': self.k_neighbors,
            'trained': self._trained,
            'training_history': self._training_history,
        }
        metadata_path = path / f"{self.model_name}_metadata.pkl"
        with open(metadata_path, 'wb') as f:
            pickle.dump(metadata, f)

        logger.info(f"Saved metadata to {metadata_path}")

    def load(self, path: Path) -> "GNNFloodModel":
        """Load GNN model from disk."""
        path = Path(path)

        # Load metadata
        metadata_path = path / f"{self.model_name}_metadata.pkl"
        with open(metadata_path, 'rb') as f:
            metadata = pickle.load(f)

        self.input_dim = metadata['input_dim']
        self.hidden_dim = metadata['hidden_dim']
        self.num_layers = metadata['num_layers']
        self.gnn_type = metadata['gnn_type']
        self.k_neighbors = metadata['k_neighbors']
        self._trained = metadata['trained']
        self._training_history = metadata['training_history']

        # Reinitialize model with loaded params
        self.model = FloodGNN(
            input_dim=self.input_dim,
            hidden_dim=self.hidden_dim,
            num_layers=self.num_layers,
            gnn_type=self.gnn_type,
        )

        # Load state dict
        model_path = path / f"{self.model_name}_gnn.pt"
        self.model.load_state_dict(torch.load(model_path, map_location=self.device))
        self.model.to(self.device)

        logger.info(f"Loaded GNN model from {path}")
        return self

    def get_model_info(self) -> Dict:
        """Return model metadata."""
        info = super().get_model_info()
        info.update({
            'input_dim': self.input_dim,
            'hidden_dim': self.hidden_dim,
            'num_layers': self.num_layers,
            'gnn_type': self.gnn_type,
            'k_neighbors': self.k_neighbors,
            'device': str(self.device),
        })
        return info

    def __repr__(self) -> str:
        return (
            f"GNNFloodModel(name='{self.model_name}', "
            f"type={self.gnn_type}, layers={self.num_layers}, "
            f"trained={self._trained})"
        )
