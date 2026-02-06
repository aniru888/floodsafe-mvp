"""
Custom loss functions for flood prediction.

Focal Loss handles class imbalance by down-weighting easy examples
and focusing on hard-to-classify samples (rare flood events).

Reference: Lin et al., "Focal Loss for Dense Object Detection" (2017)
"""
import torch
import torch.nn as nn
import torch.nn.functional as F


class FocalLoss(nn.Module):
    """
    Focal Loss for binary classification with class imbalance.

    FL(p_t) = -alpha_t * (1 - p_t)^gamma * log(p_t)

    Args:
        alpha: Weighting factor for positive class (default 0.25)
        gamma: Focusing parameter (default 2.0)
        reduction: 'mean', 'sum', or 'none'
    """

    def __init__(self, alpha: float = 0.25, gamma: float = 2.0, reduction: str = 'mean'):
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma
        self.reduction = reduction

    def forward(self, inputs: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        """
        Args:
            inputs: Logits from model (before sigmoid), shape (N,) or (N, 1)
            targets: Binary labels, shape (N,) or (N, 1)

        Returns:
            Focal loss value
        """
        # Flatten inputs
        inputs = inputs.view(-1)
        targets = targets.view(-1).float()

        # Calculate BCE loss (without reduction)
        bce_loss = F.binary_cross_entropy_with_logits(
            inputs, targets, reduction='none'
        )

        # Calculate probability
        probs = torch.sigmoid(inputs)
        p_t = probs * targets + (1 - probs) * (1 - targets)

        # Apply focal modulation
        focal_weight = (1 - p_t) ** self.gamma

        # Apply alpha weighting
        alpha_t = self.alpha * targets + (1 - self.alpha) * (1 - targets)

        # Final focal loss
        focal_loss = alpha_t * focal_weight * bce_loss

        if self.reduction == 'mean':
            return focal_loss.mean()
        elif self.reduction == 'sum':
            return focal_loss.sum()
        else:
            return focal_loss


class BinaryFocalLoss(FocalLoss):
    """Alias for FocalLoss with flood-optimized defaults."""

    def __init__(self, alpha: float = 0.75, gamma: float = 2.0):
        """
        Flood prediction defaults:
        - alpha=0.75: Higher weight for positive (flood) class
        - gamma=2.0: Strong focus on hard examples
        """
        super().__init__(alpha=alpha, gamma=gamma, reduction='mean')


class CombinedLoss(nn.Module):
    """
    Combined loss: Focal Loss + Dice Loss for better gradient flow.
    """

    def __init__(self, focal_weight: float = 0.7, dice_weight: float = 0.3,
                 alpha: float = 0.75, gamma: float = 2.0):
        super().__init__()
        self.focal = FocalLoss(alpha=alpha, gamma=gamma)
        self.focal_weight = focal_weight
        self.dice_weight = dice_weight

    def forward(self, inputs: torch.Tensor, targets: torch.Tensor) -> torch.Tensor:
        focal_loss = self.focal(inputs, targets)

        # Dice loss
        probs = torch.sigmoid(inputs.view(-1))
        targets_flat = targets.view(-1).float()
        intersection = (probs * targets_flat).sum()
        dice_loss = 1 - (2 * intersection + 1) / (probs.sum() + targets_flat.sum() + 1)

        return self.focal_weight * focal_loss + self.dice_weight * dice_loss
