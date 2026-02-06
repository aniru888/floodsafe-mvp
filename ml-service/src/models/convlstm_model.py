"""
CNN-ConvLSTM model for flood prediction.

Architecture based on verified research for Delhi:
- ArXiv 2024: "Deep Learning for Short-Term Precipitation Prediction in Four Major Indian Cities"
- Config: 64 conv filters, 32 LSTM units, attention mechanism

Input: (batch, sequence_length, features) - e.g., (32, 30, 37)
Output: (batch, 1) - flood probability
"""
import torch
import torch.nn as nn
import numpy as np
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
import logging
import json

from .base import FloodPredictionModel

logger = logging.getLogger(__name__)


class TemporalConvBlock(nn.Module):
    """1D convolution over temporal dimension with residual connection."""

    def __init__(self, in_channels: int, out_channels: int, kernel_size: int = 3):
        super().__init__()
        self.conv = nn.Conv1d(
            in_channels, out_channels, kernel_size,
            padding=kernel_size // 2
        )
        self.bn = nn.BatchNorm1d(out_channels)
        self.relu = nn.ReLU()

        # Residual projection if dimensions differ
        self.residual = nn.Conv1d(in_channels, out_channels, 1) if in_channels != out_channels else nn.Identity()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: (batch, channels, seq_len)
        """
        residual = self.residual(x)
        out = self.relu(self.bn(self.conv(x)))
        return out + residual


class SelfAttention(nn.Module):
    """Self-attention over temporal sequence."""

    def __init__(self, hidden_dim: int, num_heads: int = 4):
        super().__init__()
        self.attention = nn.MultiheadAttention(
            embed_dim=hidden_dim,
            num_heads=num_heads,
            batch_first=True
        )
        self.norm = nn.LayerNorm(hidden_dim)

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            x: (batch, seq_len, hidden_dim)

        Returns:
            output: (batch, seq_len, hidden_dim)
            attention_weights: (batch, seq_len, seq_len)
        """
        attn_out, attn_weights = self.attention(x, x, x)
        out = self.norm(x + attn_out)
        return out, attn_weights


class CNNConvLSTM(nn.Module):
    """
    CNN-ConvLSTM model for flood prediction.

    Architecture:
    1. Temporal Conv blocks (extract local patterns)
    2. Bidirectional LSTM (capture temporal dependencies)
    3. Self-attention (focus on flood-relevant timesteps)
    4. Dense layers (final prediction)
    """

    def __init__(
        self,
        input_dim: int = 37,
        conv_filters: int = 64,
        lstm_units: int = 32,
        num_conv_layers: int = 2,
        dropout: float = 0.2,
        num_attention_heads: int = 4
    ):
        super().__init__()
        self.model_name = "ConvLSTM-Flood"
        self.input_dim = input_dim
        self.conv_filters = conv_filters
        self.lstm_units = lstm_units

        # Temporal convolution layers
        self.conv_layers = nn.ModuleList()
        in_ch = input_dim
        for i in range(num_conv_layers):
            out_ch = conv_filters if i == 0 else conv_filters
            self.conv_layers.append(TemporalConvBlock(in_ch, out_ch))
            in_ch = out_ch

        # Bidirectional LSTM
        self.lstm = nn.LSTM(
            input_size=conv_filters,
            hidden_size=lstm_units,
            num_layers=2,
            batch_first=True,
            bidirectional=True,
            dropout=dropout
        )

        # Self-attention
        self.attention = SelfAttention(lstm_units * 2, num_attention_heads)

        # Output layers
        self.dropout = nn.Dropout(dropout)
        self.fc1 = nn.Linear(lstm_units * 2, 128)
        self.fc2 = nn.Linear(128, 64)
        self.fc3 = nn.Linear(64, 1)
        self.relu = nn.ReLU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: (batch, seq_len, input_dim) - e.g., (32, 30, 37)

        Returns:
            logits: (batch, 1) - raw logits before sigmoid
        """
        batch_size, seq_len, _ = x.shape

        # Conv expects (batch, channels, seq_len)
        x = x.permute(0, 2, 1)

        # Apply conv layers
        for conv in self.conv_layers:
            x = conv(x)

        # Back to (batch, seq_len, channels)
        x = x.permute(0, 2, 1)

        # LSTM
        lstm_out, _ = self.lstm(x)  # (batch, seq_len, lstm_units*2)

        # Attention
        attn_out, self._attention_weights = self.attention(lstm_out)

        # Global average pooling over time
        pooled = attn_out.mean(dim=1)  # (batch, lstm_units*2)

        # Dense layers
        out = self.dropout(self.relu(self.fc1(pooled)))
        out = self.dropout(self.relu(self.fc2(out)))
        logits = self.fc3(out)  # (batch, 1)

        return logits

    def predict_proba(self, x: torch.Tensor) -> np.ndarray:
        """Return probability predictions."""
        self.eval()
        with torch.no_grad():
            logits = self.forward(x)
            probs = torch.sigmoid(logits)
        return probs.cpu().numpy()

    def get_attention_weights(self) -> Optional[torch.Tensor]:
        """Return last attention weights for interpretability."""
        return getattr(self, '_attention_weights', None)

    def save(self, save_dir: Path):
        """Save model to directory."""
        save_dir = Path(save_dir)
        save_dir.mkdir(parents=True, exist_ok=True)

        torch.save(self.state_dict(), save_dir / "model.pt")

        config = {
            "model_name": self.model_name,
            "input_dim": self.input_dim,
            "conv_filters": self.conv_filters,
            "lstm_units": self.lstm_units,
        }
        with open(save_dir / "config.json", 'w') as f:
            json.dump(config, f, indent=2)

    @classmethod
    def load(cls, load_dir: Path) -> "CNNConvLSTM":
        """Load model from directory."""
        load_dir = Path(load_dir)

        with open(load_dir / "config.json") as f:
            config = json.load(f)

        model = cls(
            input_dim=config.get("input_dim", 37),
            conv_filters=config.get("conv_filters", 64),
            lstm_units=config.get("lstm_units", 32)
        )
        model.load_state_dict(torch.load(load_dir / "model.pt", map_location='cpu'))
        return model


class ConvLSTMFloodModel(FloodPredictionModel):
    """
    ConvLSTM-based flood prediction model implementing FloodPredictionModel interface.

    Features:
    - 1D temporal convolutions for local pattern extraction
    - Bidirectional LSTM for temporal dependencies
    - Self-attention mechanism for interpretability
    - Focal loss for class imbalance handling
    - Automatic device detection (CUDA/CPU)
    """

    def __init__(
        self,
        input_dim: int = 37,
        conv_filters: int = 64,
        lstm_units: int = 32,
        num_conv_layers: int = 2,
        dropout: float = 0.2,
        num_attention_heads: int = 4,
        device: Optional[str] = None
    ):
        """
        Initialize ConvLSTM flood model.

        Args:
            input_dim: Number of features per timestep
            conv_filters: Number of convolutional filters
            lstm_units: LSTM hidden size
            num_conv_layers: Number of temporal conv layers
            dropout: Dropout rate
            num_attention_heads: Number of attention heads
            device: 'cuda', 'cpu', or None for auto-detection
        """
        super().__init__(model_name='ConvLSTM-Flood')

        self.input_dim = input_dim
        self.conv_filters = conv_filters
        self.lstm_units = lstm_units
        self.num_conv_layers = num_conv_layers
        self.dropout = dropout
        self.num_attention_heads = num_attention_heads

        # Device setup
        if device is None:
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        else:
            self.device = torch.device(device)

        logger.info(f"Using device: {self.device}")

        # Initialize network
        self.model = CNNConvLSTM(
            input_dim=input_dim,
            conv_filters=conv_filters,
            lstm_units=lstm_units,
            num_conv_layers=num_conv_layers,
            dropout=dropout,
            num_attention_heads=num_attention_heads
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
        epochs: int = 100,
        batch_size: int = 32,
        validation_split: float = 0.2,
        learning_rate: float = 1e-3,
        patience: int = 10,
        min_delta: float = 1e-4,
        grad_clip: float = 1.0
    ) -> "ConvLSTMFloodModel":
        """
        Train the ConvLSTM model.

        Args:
            X: Temporal features, shape (n_samples, seq_length, n_features)
            y: Binary labels, shape (n_samples,) or (n_samples, 1)
            epochs: Maximum training epochs
            batch_size: Batch size
            validation_split: Fraction of data for validation
            learning_rate: Learning rate
            patience: Early stopping patience
            min_delta: Minimum improvement threshold
            grad_clip: Gradient clipping threshold

        Returns:
            self
        """
        if X.shape[0] != y.shape[0]:
            raise ValueError(f"X and y must have same number of samples: {X.shape[0]} != {y.shape[0]}")

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

        train_loader = self._create_dataloader(X_train, y_train, batch_size, shuffle=True)
        val_loader = self._create_dataloader(X_val, y_val, batch_size, shuffle=False)

        # Initialize training components
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=learning_rate)

        # Import focal loss
        from .losses import BinaryFocalLoss
        self.criterion = BinaryFocalLoss()

        self.scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
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
        batch_size: int,
        shuffle: bool
    ):
        """Create PyTorch DataLoader from numpy arrays."""
        from torch.utils.data import DataLoader, TensorDataset

        X_tensor = torch.FloatTensor(X)
        y_tensor = torch.FloatTensor(y)
        dataset = TensorDataset(X_tensor, y_tensor)
        return DataLoader(dataset, batch_size=batch_size, shuffle=shuffle)

    def _train_epoch(self, dataloader, grad_clip: float) -> float:
        """Train for one epoch."""
        self.model.train()
        total_loss = 0.0
        n_batches = 0

        for X_batch, y_batch in dataloader:
            X_batch = X_batch.to(self.device)
            y_batch = y_batch.to(self.device)

            # Forward pass
            logits = self.model(X_batch)

            # Compute loss
            loss = self.criterion(logits.squeeze(), y_batch.squeeze())

            # Backward pass
            self.optimizer.zero_grad()
            loss.backward()

            # Gradient clipping
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), grad_clip)

            self.optimizer.step()

            total_loss += loss.item()
            n_batches += 1

        return total_loss / n_batches

    def _validate_epoch(self, dataloader) -> float:
        """Validate for one epoch."""
        self.model.eval()
        total_loss = 0.0
        n_batches = 0

        with torch.no_grad():
            for X_batch, y_batch in dataloader:
                X_batch = X_batch.to(self.device)
                y_batch = y_batch.to(self.device)

                logits = self.model(X_batch)
                loss = self.criterion(logits.squeeze(), y_batch.squeeze())

                total_loss += loss.item()
                n_batches += 1

        return total_loss / n_batches

    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Make binary predictions (0 or 1).

        Args:
            X: Temporal features, shape (n_samples, seq_length, n_features)

        Returns:
            Binary predictions, shape (n_samples,)
        """
        probas = self.predict_proba(X)
        return (probas >= 0.5).astype(int).flatten()

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """
        Predict flood probability.

        Args:
            X: Temporal features, shape (n_samples, seq_length, n_features)

        Returns:
            Probability predictions, shape (n_samples, 1)
        """
        if not self._trained:
            raise RuntimeError("Model must be trained before prediction")

        self.model.eval()
        X_tensor = torch.FloatTensor(X).to(self.device)

        with torch.no_grad():
            logits = self.model(X_tensor)
            probs = torch.sigmoid(logits)

        return probs.cpu().numpy()

    def get_attention_weights(self, X: np.ndarray) -> np.ndarray:
        """
        Extract attention weights for interpretability.

        Shows which time steps the model focuses on when making predictions.

        Args:
            X: Temporal features, shape (n_samples, seq_length, n_features)

        Returns:
            Attention weights, shape (n_samples, seq_length, seq_length)
        """
        if not self._trained:
            raise RuntimeError("Model must be trained before extracting attention")

        self.model.eval()
        X_tensor = torch.FloatTensor(X).to(self.device)

        with torch.no_grad():
            _ = self.model(X_tensor)
            attention_weights = self.model.get_attention_weights()

        return attention_weights.cpu().numpy() if attention_weights is not None else None

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
                'input_dim': self.input_dim,
                'conv_filters': self.conv_filters,
                'lstm_units': self.lstm_units,
                'num_conv_layers': self.num_conv_layers,
                'dropout': self.dropout,
                'num_attention_heads': self.num_attention_heads,
            },
            'trained': self._trained
        }, model_path)

        logger.info(f"Model saved to {model_path}")

    def load(self, path: Path) -> "ConvLSTMFloodModel":
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
        if config['input_dim'] != self.input_dim:
            logger.warning(
                f"Loaded model input_dim ({config['input_dim']}) "
                f"differs from current ({self.input_dim})"
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
            'architecture': 'CNN-ConvLSTM + Self-Attention',
            'input_dim': self.input_dim,
            'conv_filters': self.conv_filters,
            'lstm_units': self.lstm_units,
            'num_conv_layers': self.num_conv_layers,
            'num_attention_heads': self.num_attention_heads,
            'total_parameters': self._count_parameters(),
            'device': str(self.device),
            'dropout': self.dropout
        })
        return info
