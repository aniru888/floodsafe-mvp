"""
LSTM-based flood prediction model with self-attention mechanism.

Architecture:
- Bidirectional LSTM for temporal sequence features
- Self-attention mechanism on LSTM outputs for interpretability
- MLP for AlphaEarth 64-dimensional spatial embeddings
- Combined output through final fully connected layers
- Sigmoid activation for probability output (0-1 range)

References:
- ml_flood architecture (ECMWF)
- AlphaEarth embeddings (Google Earth Engine)
"""

from pathlib import Path
from typing import Dict, Optional, Tuple
import logging

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from torch.optim import Adam
from torch.optim.lr_scheduler import ReduceLROnPlateau

from .base import FloodPredictionModel
from ..core.config import settings

logger = logging.getLogger(__name__)


class AttentionLayer(nn.Module):
    """
    Self-attention mechanism for LSTM outputs.

    Computes attention weights over the temporal sequence,
    allowing the model to focus on important time steps.
    """

    def __init__(self, hidden_size: int):
        """
        Initialize attention layer.

        Args:
            hidden_size: Size of LSTM hidden states (bidirectional, so doubled)
        """
        super(AttentionLayer, self).__init__()
        self.hidden_size = hidden_size

        # Attention mechanism
        self.attention_weights = nn.Linear(hidden_size, 1, bias=False)

    def forward(self, lstm_outputs: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Apply attention to LSTM outputs.

        Args:
            lstm_outputs: LSTM outputs of shape (batch_size, seq_length, hidden_size)

        Returns:
            context_vector: Weighted sum of LSTM outputs (batch_size, hidden_size)
            attention_weights: Attention weights (batch_size, seq_length)
        """
        # Calculate attention scores
        # Shape: (batch_size, seq_length, 1)
        attention_scores = self.attention_weights(lstm_outputs)

        # Apply softmax to get attention weights
        # Shape: (batch_size, seq_length, 1)
        attention_weights = torch.softmax(attention_scores, dim=1)

        # Compute context vector as weighted sum
        # Shape: (batch_size, hidden_size)
        context_vector = torch.sum(attention_weights * lstm_outputs, dim=1)

        # Return context and weights (squeeze for easier use)
        return context_vector, attention_weights.squeeze(-1)


class FloodLSTM(nn.Module):
    """
    Main LSTM network for flood prediction.

    Combines temporal features (LSTM + attention) with spatial embeddings
    (AlphaEarth) for comprehensive flood risk prediction.
    """

    def __init__(
        self,
        input_size: int,
        hidden_size: int = 128,
        num_layers: int = 2,
        embedding_dim: int = 64,
        dropout: float = 0.2
    ):
        """
        Initialize FloodLSTM network.

        Args:
            input_size: Number of temporal features per timestep
            hidden_size: LSTM hidden state size
            num_layers: Number of LSTM layers
            embedding_dim: Dimension of spatial embeddings (AlphaEarth = 64)
            dropout: Dropout rate for regularization
        """
        super(FloodLSTM, self).__init__()

        self.input_size = input_size
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.embedding_dim = embedding_dim

        # Bidirectional LSTM for temporal features
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            bidirectional=True,
            dropout=dropout if num_layers > 1 else 0
        )

        # Self-attention mechanism (bidirectional doubles hidden size)
        self.attention = AttentionLayer(hidden_size * 2)

        # MLP for AlphaEarth spatial embeddings
        self.embedding_mlp = nn.Sequential(
            nn.Linear(embedding_dim, 128),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(dropout)
        )

        # Combined features: LSTM context + embeddings
        combined_size = hidden_size * 2 + 64

        # Final output layers
        self.output_layers = nn.Sequential(
            nn.Linear(combined_size, 128),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(64, 1),
            nn.Sigmoid()  # Output probability [0, 1]
        )

    def forward(
        self,
        temporal_features: torch.Tensor,
        spatial_embeddings: Optional[torch.Tensor] = None
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Forward pass.

        Args:
            temporal_features: Shape (batch_size, seq_length, input_size)
            spatial_embeddings: Shape (batch_size, embedding_dim), optional

        Returns:
            predictions: Flood probability (batch_size, 1)
            attention_weights: Attention weights (batch_size, seq_length)
        """
        # LSTM forward pass
        lstm_out, _ = self.lstm(temporal_features)
        # Shape: (batch_size, seq_length, hidden_size * 2)

        # Apply attention
        context_vector, attention_weights = self.attention(lstm_out)
        # context_vector: (batch_size, hidden_size * 2)
        # attention_weights: (batch_size, seq_length)

        # Process spatial embeddings if provided
        if spatial_embeddings is not None:
            embedding_features = self.embedding_mlp(spatial_embeddings)
            # Shape: (batch_size, 64)

            # Combine temporal and spatial features
            combined = torch.cat([context_vector, embedding_features], dim=1)
        else:
            # Use only temporal features (zero-pad embedding dimension)
            zero_embeddings = torch.zeros(
                context_vector.size(0), 64,
                device=context_vector.device
            )
            combined = torch.cat([context_vector, zero_embeddings], dim=1)

        # Final prediction
        predictions = self.output_layers(combined)

        return predictions, attention_weights


class LSTMFloodModel(FloodPredictionModel):
    """
    LSTM-based flood prediction model implementing FloodPredictionModel interface.

    Features:
    - Bidirectional LSTM with self-attention
    - AlphaEarth spatial embedding integration
    - Early stopping with validation monitoring
    - Gradient clipping for stability
    - Automatic device detection (CUDA/CPU)
    """

    def __init__(
        self,
        input_size: int,
        hidden_size: Optional[int] = None,
        num_layers: Optional[int] = None,
        embedding_dim: int = 64,
        dropout: float = 0.2,
        device: Optional[str] = None
    ):
        """
        Initialize LSTM flood model.

        Args:
            input_size: Number of temporal features per timestep
            hidden_size: LSTM hidden size (defaults to config)
            num_layers: Number of LSTM layers (defaults to config)
            embedding_dim: Spatial embedding dimension (64 for AlphaEarth)
            dropout: Dropout rate
            device: 'cuda', 'cpu', or None for auto-detection
        """
        super().__init__(model_name='LSTM-Attention-Flood')

        # Model configuration
        self.input_size = input_size
        self.hidden_size = hidden_size or settings.LSTM_HIDDEN_SIZE
        self.num_layers = num_layers or settings.LSTM_NUM_LAYERS
        self.embedding_dim = embedding_dim
        self.dropout = dropout

        # Device setup
        if device is None:
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        else:
            self.device = torch.device(device)

        logger.info(f"Using device: {self.device}")

        # Initialize network
        self.model = FloodLSTM(
            input_size=input_size,
            hidden_size=self.hidden_size,
            num_layers=self.num_layers,
            embedding_dim=embedding_dim,
            dropout=dropout
        ).to(self.device)

        # Training components (initialized in fit)
        self.optimizer = None
        self.criterion = None
        self.scheduler = None

        logger.info(f"Initialized {self.model_name} with {self._count_parameters()} parameters")

    def _count_parameters(self) -> int:
        """Count trainable parameters."""
        return sum(p.numel() for p in self.model.parameters() if p.requires_grad)

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        embeddings: Optional[np.ndarray] = None,
        epochs: int = 100,
        batch_size: Optional[int] = None,
        validation_split: float = 0.2,
        learning_rate: Optional[float] = None,
        patience: int = 10,
        min_delta: float = 1e-4,
        grad_clip: float = 1.0
    ) -> "LSTMFloodModel":
        """
        Train the LSTM model.

        Args:
            X: Temporal features, shape (n_samples, seq_length, n_features)
            y: Binary labels, shape (n_samples,) or (n_samples, 1)
            embeddings: Spatial embeddings, shape (n_samples, embedding_dim)
            epochs: Maximum training epochs
            batch_size: Batch size (defaults to config)
            validation_split: Fraction of data for validation
            learning_rate: Learning rate (defaults to config)
            patience: Early stopping patience
            min_delta: Minimum improvement threshold
            grad_clip: Gradient clipping threshold

        Returns:
            self
        """
        if X.shape[0] != y.shape[0]:
            raise ValueError(f"X and y must have same number of samples: {X.shape[0]} != {y.shape[0]}")

        if embeddings is not None and embeddings.shape[0] != X.shape[0]:
            raise ValueError(f"Embeddings must match X samples: {embeddings.shape[0]} != {X.shape[0]}")

        batch_size = batch_size or settings.BATCH_SIZE
        learning_rate = learning_rate or settings.LEARNING_RATE

        # Reshape y if needed
        if y.ndim == 1:
            y = y.reshape(-1, 1)

        # Train/validation split
        n_samples = X.shape[0]
        n_val = int(n_samples * validation_split)
        n_train = n_samples - n_val

        indices = np.random.permutation(n_samples)
        train_idx, val_idx = indices[:n_train], indices[n_train:]

        # Prepare datasets
        X_train, X_val = X[train_idx], X[val_idx]
        y_train, y_val = y[train_idx], y[val_idx]

        train_loader = self._create_dataloader(
            X_train,
            y_train,
            embeddings[train_idx] if embeddings is not None else None,
            batch_size,
            shuffle=True
        )

        val_loader = self._create_dataloader(
            X_val,
            y_val,
            embeddings[val_idx] if embeddings is not None else None,
            batch_size,
            shuffle=False
        )

        # Initialize training components
        self.optimizer = Adam(self.model.parameters(), lr=learning_rate)
        self.criterion = nn.BCELoss()
        self.scheduler = ReduceLROnPlateau(
            self.optimizer,
            mode='min',
            factor=0.5,
            patience=patience // 2
        )

        # Training loop
        self._training_history = {
            'train_loss': [],
            'val_loss': [],
            'learning_rates': []
        }

        best_val_loss = float('inf')
        patience_counter = 0

        logger.info(f"Training {self.model_name} for {epochs} epochs...")
        logger.info(f"Train samples: {n_train}, Validation samples: {n_val}")

        for epoch in range(epochs):
            # Training phase
            train_loss = self._train_epoch(train_loader, grad_clip)

            # Validation phase
            val_loss = self._validate_epoch(val_loader)

            # Record history
            self._training_history['train_loss'].append(train_loss)
            self._training_history['val_loss'].append(val_loss)
            self._training_history['learning_rates'].append(
                self.optimizer.param_groups[0]['lr']
            )

            # Learning rate scheduling
            self.scheduler.step(val_loss)

            # Logging
            if (epoch + 1) % 5 == 0 or epoch == 0:
                logger.info(
                    f"Epoch {epoch+1}/{epochs} - "
                    f"Train Loss: {train_loss:.4f}, Val Loss: {val_loss:.4f}"
                )

            # Early stopping check
            if val_loss < best_val_loss - min_delta:
                best_val_loss = val_loss
                patience_counter = 0
                # Save best model state
                self._best_model_state = {
                    k: v.cpu().clone() for k, v in self.model.state_dict().items()
                }
            else:
                patience_counter += 1
                if patience_counter >= patience:
                    logger.info(f"Early stopping triggered at epoch {epoch+1}")
                    # Restore best model
                    self.model.load_state_dict(self._best_model_state)
                    break

        self._trained = True
        logger.info(f"Training completed. Best validation loss: {best_val_loss:.4f}")

        return self

    def _create_dataloader(
        self,
        X: np.ndarray,
        y: np.ndarray,
        embeddings: Optional[np.ndarray],
        batch_size: int,
        shuffle: bool
    ) -> DataLoader:
        """Create PyTorch DataLoader from numpy arrays."""
        X_tensor = torch.FloatTensor(X)
        y_tensor = torch.FloatTensor(y)

        if embeddings is not None:
            embeddings_tensor = torch.FloatTensor(embeddings)
            dataset = TensorDataset(X_tensor, embeddings_tensor, y_tensor)
        else:
            dataset = TensorDataset(X_tensor, y_tensor)

        return DataLoader(dataset, batch_size=batch_size, shuffle=shuffle)

    def _train_epoch(self, dataloader: DataLoader, grad_clip: float) -> float:
        """Train for one epoch."""
        self.model.train()
        total_loss = 0.0
        n_batches = 0

        for batch in dataloader:
            if len(batch) == 3:  # With embeddings
                X_batch, emb_batch, y_batch = batch
                X_batch = X_batch.to(self.device)
                emb_batch = emb_batch.to(self.device)
                y_batch = y_batch.to(self.device)

                # Forward pass
                predictions, _ = self.model(X_batch, emb_batch)
            else:  # Without embeddings
                X_batch, y_batch = batch
                X_batch = X_batch.to(self.device)
                y_batch = y_batch.to(self.device)

                predictions, _ = self.model(X_batch, None)

            # Compute loss
            loss = self.criterion(predictions, y_batch)

            # Backward pass
            self.optimizer.zero_grad()
            loss.backward()

            # Gradient clipping
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), grad_clip)

            self.optimizer.step()

            total_loss += loss.item()
            n_batches += 1

        return total_loss / n_batches

    def _validate_epoch(self, dataloader: DataLoader) -> float:
        """Validate for one epoch."""
        self.model.eval()
        total_loss = 0.0
        n_batches = 0

        with torch.no_grad():
            for batch in dataloader:
                if len(batch) == 3:  # With embeddings
                    X_batch, emb_batch, y_batch = batch
                    X_batch = X_batch.to(self.device)
                    emb_batch = emb_batch.to(self.device)
                    y_batch = y_batch.to(self.device)

                    predictions, _ = self.model(X_batch, emb_batch)
                else:  # Without embeddings
                    X_batch, y_batch = batch
                    X_batch = X_batch.to(self.device)
                    y_batch = y_batch.to(self.device)

                    predictions, _ = self.model(X_batch, None)

                loss = self.criterion(predictions, y_batch)
                total_loss += loss.item()
                n_batches += 1

        return total_loss / n_batches

    def predict(self, X: np.ndarray, embeddings: Optional[np.ndarray] = None) -> np.ndarray:
        """
        Make binary predictions (0 or 1).

        Args:
            X: Temporal features, shape (n_samples, seq_length, n_features)
            embeddings: Spatial embeddings, shape (n_samples, embedding_dim)

        Returns:
            Binary predictions, shape (n_samples,)
        """
        probas = self.predict_proba(X, embeddings)
        return (probas >= 0.5).astype(int).flatten()

    def predict_proba(
        self,
        X: np.ndarray,
        embeddings: Optional[np.ndarray] = None
    ) -> np.ndarray:
        """
        Predict flood probability.

        Args:
            X: Temporal features, shape (n_samples, seq_length, n_features)
            embeddings: Spatial embeddings, shape (n_samples, embedding_dim)

        Returns:
            Probability predictions, shape (n_samples, 1)
        """
        if not self._trained:
            raise RuntimeError("Model must be trained before prediction")

        self.model.eval()

        X_tensor = torch.FloatTensor(X).to(self.device)
        emb_tensor = torch.FloatTensor(embeddings).to(self.device) if embeddings is not None else None

        with torch.no_grad():
            predictions, _ = self.model(X_tensor, emb_tensor)

        return predictions.cpu().numpy()

    def get_attention_weights(
        self,
        X: np.ndarray,
        embeddings: Optional[np.ndarray] = None
    ) -> np.ndarray:
        """
        Extract attention weights for interpretability.

        Shows which time steps the model focuses on when making predictions.

        Args:
            X: Temporal features, shape (n_samples, seq_length, n_features)
            embeddings: Spatial embeddings, shape (n_samples, embedding_dim)

        Returns:
            Attention weights, shape (n_samples, seq_length)
        """
        if not self._trained:
            raise RuntimeError("Model must be trained before extracting attention")

        self.model.eval()

        X_tensor = torch.FloatTensor(X).to(self.device)
        emb_tensor = torch.FloatTensor(embeddings).to(self.device) if embeddings is not None else None

        with torch.no_grad():
            _, attention_weights = self.model(X_tensor, emb_tensor)

        return attention_weights.cpu().numpy()

    def save(self, path: Path) -> None:
        """
        Save model to disk.

        Args:
            path: Directory path to save model
        """
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)

        # Save model state
        model_path = path / "model.pt"
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict() if self.optimizer else None,
            'training_history': self._training_history,
            'config': {
                'input_size': self.input_size,
                'hidden_size': self.hidden_size,
                'num_layers': self.num_layers,
                'embedding_dim': self.embedding_dim,
                'dropout': self.dropout,
            },
            'trained': self._trained
        }, model_path)

        logger.info(f"Model saved to {model_path}")

    def load(self, path: Path) -> "LSTMFloodModel":
        """
        Load model from disk.

        Args:
            path: Directory path containing saved model

        Returns:
            self
        """
        path = Path(path)
        model_path = path / "model.pt"

        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")

        # Load checkpoint
        checkpoint = torch.load(model_path, map_location=self.device)

        # Restore configuration
        config = checkpoint['config']
        if config['input_size'] != self.input_size:
            logger.warning(
                f"Loaded model input_size ({config['input_size']}) "
                f"differs from current ({self.input_size})"
            )

        # Load model state
        self.model.load_state_dict(checkpoint['model_state_dict'])

        # Restore training state
        self._training_history = checkpoint['training_history']
        self._trained = checkpoint['trained']

        if checkpoint['optimizer_state_dict'] and self.optimizer:
            self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])

        logger.info(f"Model loaded from {model_path}")

        return self

    def get_model_info(self) -> Dict:
        """Return detailed model metadata."""
        info = super().get_model_info()
        info.update({
            'architecture': 'Bidirectional LSTM + Self-Attention',
            'input_size': self.input_size,
            'hidden_size': self.hidden_size,
            'num_layers': self.num_layers,
            'embedding_dim': self.embedding_dim,
            'total_parameters': self._count_parameters(),
            'device': str(self.device),
            'dropout': self.dropout
        })
        return info
