#!/usr/bin/env python3
"""
MobileNetV3-Small Binary Flood Classifier Training Script.

Trains a lightweight binary classifier (flood vs no_flood) using:
- MobileNetV3-Small pretrained on ImageNet
- Transfer learning (freeze backbone, train classifier)
- Data augmentation for robustness

Target: 90%+ accuracy on test set

Usage:
    python -m apps.ml-service.scripts.train_flood_binary

    # With custom epochs
    python -m apps.ml-service.scripts.train_flood_binary --epochs 20

    # Continue training from checkpoint
    python -m apps.ml-service.scripts.train_flood_binary --resume
"""

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple, Optional

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from torchvision import datasets, models, transforms
from tqdm import tqdm

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
ML_SERVICE_DIR = Path(__file__).parent.parent
DATA_DIR = ML_SERVICE_DIR / "data"
DATASET_DIR = DATA_DIR / "india_flood_dataset"
MODEL_DIR = ML_SERVICE_DIR / "models" / "flood_classifier"

# Training configuration
TRAINING_CONFIG = {
    "model": "mobilenet_v3_small",
    "input_size": 224,
    "batch_size": 32,
    "epochs": 10,
    "learning_rate": 0.001,
    "weight_decay": 1e-4,
    "num_workers": 4,
    "freeze_backbone": True,  # Only train classifier head initially
    "unfreeze_after": 5,      # Unfreeze backbone after N epochs for fine-tuning
}

# ImageNet normalization (required for pretrained models)
IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


def get_transforms() -> Dict[str, transforms.Compose]:
    """
    Create data augmentation transforms.

    Training: Heavy augmentation for robustness
    Validation/Test: Only resize and normalize
    """
    input_size = TRAINING_CONFIG["input_size"]

    train_transforms = transforms.Compose([
        transforms.Resize((input_size, input_size)),
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.RandomRotation(degrees=15),
        transforms.ColorJitter(
            brightness=0.2,
            contrast=0.2,
            saturation=0.2,
            hue=0.1,
        ),
        transforms.RandomAffine(
            degrees=0,
            translate=(0.1, 0.1),
            scale=(0.9, 1.1),
        ),
        transforms.ToTensor(),
        transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
    ])

    val_transforms = transforms.Compose([
        transforms.Resize((input_size, input_size)),
        transforms.ToTensor(),
        transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
    ])

    return {
        "train": train_transforms,
        "val": val_transforms,
        "test": val_transforms,
    }


def create_dataloaders(
    dataset_dir: Path = DATASET_DIR,
    batch_size: int = None,
    num_workers: int = None,
) -> Dict[str, DataLoader]:
    """
    Create DataLoaders for train/val/test splits.

    Uses ImageFolder to automatically load from:
    dataset_dir/
    ├── train/{flood,no_flood}/
    ├── val/{flood,no_flood}/
    └── test/{flood,no_flood}/
    """
    batch_size = batch_size or TRAINING_CONFIG["batch_size"]
    num_workers = num_workers or TRAINING_CONFIG["num_workers"]

    transforms_dict = get_transforms()
    dataloaders = {}

    for split in ["train", "val", "test"]:
        split_dir = dataset_dir / split

        if not split_dir.exists():
            logger.warning(f"{split} directory not found: {split_dir}")
            continue

        dataset = datasets.ImageFolder(
            str(split_dir),
            transform=transforms_dict[split],
        )

        shuffle = (split == "train")

        dataloaders[split] = DataLoader(
            dataset,
            batch_size=batch_size,
            shuffle=shuffle,
            num_workers=num_workers,
            pin_memory=True,
        )

        logger.info(f"Loaded {split}: {len(dataset)} images, {len(dataloaders[split])} batches")

    return dataloaders


def create_model(num_classes: int = 2, pretrained: bool = True) -> nn.Module:
    """
    Create MobileNetV3-Small model for binary classification.

    Architecture:
    - MobileNetV3-Small backbone (pretrained on ImageNet)
    - Replace final classifier: Linear(576, 2)

    Total params: ~2.5M (mobile-friendly)
    """
    # Load pretrained MobileNetV3-Small
    weights = models.MobileNet_V3_Small_Weights.IMAGENET1K_V1 if pretrained else None
    model = models.mobilenet_v3_small(weights=weights)

    # Replace classifier head
    # MobileNetV3-Small has: classifier = Sequential(Linear(576, 1024), Hardswish, Dropout, Linear(1024, 1000))
    in_features = model.classifier[0].in_features  # 576

    model.classifier = nn.Sequential(
        nn.Linear(in_features, 256),
        nn.Hardswish(),
        nn.Dropout(p=0.2),
        nn.Linear(256, num_classes),
    )

    logger.info(f"Created MobileNetV3-Small with {num_classes} output classes")
    logger.info(f"Total parameters: {sum(p.numel() for p in model.parameters()):,}")

    return model


def freeze_backbone(model: nn.Module) -> None:
    """Freeze backbone features, only train classifier."""
    for param in model.features.parameters():
        param.requires_grad = False

    logger.info("Backbone frozen - only training classifier head")


def unfreeze_backbone(model: nn.Module) -> None:
    """Unfreeze all parameters for fine-tuning."""
    for param in model.parameters():
        param.requires_grad = True

    logger.info("Backbone unfrozen - fine-tuning entire model")


def train_epoch(
    model: nn.Module,
    dataloader: DataLoader,
    criterion: nn.Module,
    optimizer: optim.Optimizer,
    device: torch.device,
) -> Tuple[float, float]:
    """
    Train for one epoch.

    Returns:
        (loss, accuracy) tuple
    """
    model.train()
    running_loss = 0.0
    correct = 0
    total = 0

    for inputs, labels in tqdm(dataloader, desc="Training", leave=False):
        inputs = inputs.to(device)
        labels = labels.to(device)

        optimizer.zero_grad()

        outputs = model(inputs)
        loss = criterion(outputs, labels)

        loss.backward()
        optimizer.step()

        running_loss += loss.item() * inputs.size(0)
        _, predicted = outputs.max(1)
        total += labels.size(0)
        correct += predicted.eq(labels).sum().item()

    epoch_loss = running_loss / total
    epoch_acc = correct / total

    return epoch_loss, epoch_acc


def evaluate(
    model: nn.Module,
    dataloader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
) -> Tuple[float, float, Dict]:
    """
    Evaluate model on a dataset.

    Returns:
        (loss, accuracy, metrics_dict)
    """
    model.eval()
    running_loss = 0.0
    correct = 0
    total = 0

    all_preds = []
    all_labels = []

    with torch.no_grad():
        for inputs, labels in tqdm(dataloader, desc="Evaluating", leave=False):
            inputs = inputs.to(device)
            labels = labels.to(device)

            outputs = model(inputs)
            loss = criterion(outputs, labels)

            running_loss += loss.item() * inputs.size(0)
            _, predicted = outputs.max(1)
            total += labels.size(0)
            correct += predicted.eq(labels).sum().item()

            all_preds.extend(predicted.cpu().numpy())
            all_labels.extend(labels.cpu().numpy())

    epoch_loss = running_loss / total
    epoch_acc = correct / total

    # Calculate per-class metrics
    from collections import Counter
    pred_counts = Counter(all_preds)
    label_counts = Counter(all_labels)

    # Confusion matrix values (binary: 0=flood, 1=no_flood based on ImageFolder ordering)
    tp = sum(1 for p, l in zip(all_preds, all_labels) if p == 0 and l == 0)  # flood correct
    tn = sum(1 for p, l in zip(all_preds, all_labels) if p == 1 and l == 1)  # no_flood correct
    fp = sum(1 for p, l in zip(all_preds, all_labels) if p == 0 and l == 1)  # false flood
    fn = sum(1 for p, l in zip(all_preds, all_labels) if p == 1 and l == 0)  # missed flood

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    metrics = {
        "accuracy": epoch_acc,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "confusion_matrix": {
            "tp": tp, "tn": tn, "fp": fp, "fn": fn,
        },
    }

    return epoch_loss, epoch_acc, metrics


def train_model(
    model: nn.Module,
    dataloaders: Dict[str, DataLoader],
    device: torch.device,
    epochs: int = None,
    learning_rate: float = None,
    save_dir: Path = MODEL_DIR,
    resume_from: Optional[Path] = None,
) -> Dict:
    """
    Full training loop with validation.

    Features:
    - Learning rate scheduling
    - Early stopping on validation accuracy
    - Best model checkpointing
    - Training history logging
    """
    epochs = epochs or TRAINING_CONFIG["epochs"]
    learning_rate = learning_rate or TRAINING_CONFIG["learning_rate"]

    save_dir.mkdir(parents=True, exist_ok=True)

    # Loss function (CrossEntropy handles class imbalance okay for 2 classes)
    criterion = nn.CrossEntropyLoss()

    # Optimizer
    optimizer = optim.Adam(
        model.parameters(),
        lr=learning_rate,
        weight_decay=TRAINING_CONFIG["weight_decay"],
    )

    # Learning rate scheduler - reduce on plateau
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(
        optimizer,
        mode='max',
        factor=0.5,
        patience=2,
        verbose=True,
    )

    # Resume from checkpoint if specified
    start_epoch = 0
    best_val_acc = 0.0
    history = {"train_loss": [], "train_acc": [], "val_loss": [], "val_acc": []}

    if resume_from and resume_from.exists():
        checkpoint = torch.load(resume_from)
        model.load_state_dict(checkpoint["model_state_dict"])
        optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        start_epoch = checkpoint["epoch"] + 1
        best_val_acc = checkpoint.get("best_val_acc", 0)
        history = checkpoint.get("history", history)
        logger.info(f"Resumed from epoch {start_epoch}, best val acc: {best_val_acc:.4f}")

    # Freeze backbone initially
    if TRAINING_CONFIG["freeze_backbone"]:
        freeze_backbone(model)

    logger.info(f"\nStarting training for {epochs} epochs")
    logger.info(f"Device: {device}")
    logger.info(f"Learning rate: {learning_rate}")

    for epoch in range(start_epoch, epochs):
        print(f"\n{'='*60}")
        print(f"Epoch {epoch + 1}/{epochs}")
        print(f"{'='*60}")

        # Unfreeze backbone for fine-tuning after N epochs
        if epoch == TRAINING_CONFIG["unfreeze_after"] and TRAINING_CONFIG["freeze_backbone"]:
            unfreeze_backbone(model)
            # Reset optimizer with lower LR for fine-tuning
            optimizer = optim.Adam(
                model.parameters(),
                lr=learning_rate / 10,
                weight_decay=TRAINING_CONFIG["weight_decay"],
            )

        # Training
        train_loss, train_acc = train_epoch(
            model, dataloaders["train"], criterion, optimizer, device
        )
        print(f"Train Loss: {train_loss:.4f}, Train Acc: {train_acc:.4f}")

        # Validation
        val_loss, val_acc, val_metrics = evaluate(
            model, dataloaders["val"], criterion, device
        )
        print(f"Val Loss: {val_loss:.4f}, Val Acc: {val_acc:.4f}")
        print(f"Val Precision: {val_metrics['precision']:.4f}, Recall: {val_metrics['recall']:.4f}, F1: {val_metrics['f1']:.4f}")

        # Update history
        history["train_loss"].append(train_loss)
        history["train_acc"].append(train_acc)
        history["val_loss"].append(val_loss)
        history["val_acc"].append(val_acc)

        # Learning rate scheduling
        scheduler.step(val_acc)

        # Save best model
        if val_acc > best_val_acc:
            best_val_acc = val_acc
            best_model_path = save_dir / "mobilenetv3_flood_best.pt"
            torch.save({
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "optimizer_state_dict": optimizer.state_dict(),
                "best_val_acc": best_val_acc,
                "history": history,
                "config": TRAINING_CONFIG,
            }, best_model_path)
            logger.info(f"Saved best model (val acc: {best_val_acc:.4f})")

        # Save checkpoint
        checkpoint_path = save_dir / "mobilenetv3_flood_checkpoint.pt"
        torch.save({
            "epoch": epoch,
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "best_val_acc": best_val_acc,
            "history": history,
            "config": TRAINING_CONFIG,
        }, checkpoint_path)

    return {
        "best_val_acc": best_val_acc,
        "final_train_acc": history["train_acc"][-1],
        "final_val_acc": history["val_acc"][-1],
        "history": history,
    }


def test_model(
    model: nn.Module,
    dataloader: DataLoader,
    device: torch.device,
) -> Dict:
    """
    Final evaluation on test set.
    """
    criterion = nn.CrossEntropyLoss()
    test_loss, test_acc, test_metrics = evaluate(model, dataloader, criterion, device)

    print("\n" + "=" * 60)
    print("TEST SET RESULTS")
    print("=" * 60)
    print(f"Test Accuracy: {test_acc:.4f} ({test_acc*100:.2f}%)")
    print(f"Test Loss: {test_loss:.4f}")
    print(f"Precision: {test_metrics['precision']:.4f}")
    print(f"Recall: {test_metrics['recall']:.4f}")
    print(f"F1 Score: {test_metrics['f1']:.4f}")
    print("\nConfusion Matrix:")
    cm = test_metrics['confusion_matrix']
    print(f"  True Positives (flood correct): {cm['tp']}")
    print(f"  True Negatives (no_flood correct): {cm['tn']}")
    print(f"  False Positives (false alarm): {cm['fp']}")
    print(f"  False Negatives (missed flood): {cm['fn']}")

    # Target check
    target_met = test_acc >= 0.90
    print(f"\n{'✓' if target_met else '✗'} Target 90% accuracy: {'MET' if target_met else 'NOT MET'}")
    print("=" * 60)

    return {
        "test_accuracy": test_acc,
        "test_loss": test_loss,
        **test_metrics,
    }


def export_for_mobile(model: nn.Module, save_dir: Path = MODEL_DIR) -> Path:
    """
    Export model for mobile deployment using TorchScript.
    """
    model.eval()

    # Create example input
    example_input = torch.randn(1, 3, 224, 224)

    # Script the model
    scripted_model = torch.jit.script(model)

    # Save
    export_path = save_dir / "mobilenetv3_flood_mobile.pt"
    scripted_model.save(str(export_path))

    logger.info(f"Exported mobile model to {export_path}")
    logger.info(f"Model size: {export_path.stat().st_size / 1024 / 1024:.2f} MB")

    return export_path


def main():
    parser = argparse.ArgumentParser(description="Train flood binary classifier")

    parser.add_argument(
        "--epochs", type=int, default=TRAINING_CONFIG["epochs"],
        help="Number of training epochs"
    )
    parser.add_argument(
        "--batch-size", type=int, default=TRAINING_CONFIG["batch_size"],
        help="Batch size"
    )
    parser.add_argument(
        "--lr", type=float, default=TRAINING_CONFIG["learning_rate"],
        help="Learning rate"
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Resume from checkpoint"
    )
    parser.add_argument(
        "--test-only", action="store_true",
        help="Only run test evaluation on best model"
    )
    parser.add_argument(
        "--export", action="store_true",
        help="Export model for mobile after training"
    )
    parser.add_argument(
        "--dataset-dir", type=Path, default=DATASET_DIR,
        help="Dataset directory"
    )

    args = parser.parse_args()

    # Device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    logger.info(f"Using device: {device}")

    # Create dataloaders
    logger.info(f"\nLoading dataset from {args.dataset_dir}")
    dataloaders = create_dataloaders(
        args.dataset_dir,
        batch_size=args.batch_size,
    )

    if not dataloaders:
        logger.error("No data loaded! Run the collection pipeline first.")
        return 1

    # Get class names from dataset
    if "train" in dataloaders:
        class_names = dataloaders["train"].dataset.classes
        logger.info(f"Classes: {class_names}")

    # Create model
    model = create_model(num_classes=2)
    model = model.to(device)

    if args.test_only:
        # Load best model and test
        best_path = MODEL_DIR / "mobilenetv3_flood_best.pt"
        if not best_path.exists():
            logger.error(f"No best model found at {best_path}")
            return 1

        checkpoint = torch.load(best_path, map_location=device)
        model.load_state_dict(checkpoint["model_state_dict"])
        logger.info(f"Loaded best model from {best_path}")

        if "test" in dataloaders:
            test_results = test_model(model, dataloaders["test"], device)
        else:
            logger.error("No test dataloader available")
            return 1

    else:
        # Training
        resume_path = MODEL_DIR / "mobilenetv3_flood_checkpoint.pt" if args.resume else None

        training_results = train_model(
            model,
            dataloaders,
            device,
            epochs=args.epochs,
            learning_rate=args.lr,
            resume_from=resume_path,
        )

        # Test on best model
        best_path = MODEL_DIR / "mobilenetv3_flood_best.pt"
        if best_path.exists() and "test" in dataloaders:
            checkpoint = torch.load(best_path, map_location=device)
            model.load_state_dict(checkpoint["model_state_dict"])
            test_results = test_model(model, dataloaders["test"], device)

            # Save final report
            report = {
                "training": training_results,
                "test": test_results,
                "config": TRAINING_CONFIG,
                "timestamp": datetime.now().isoformat(),
            }

            report_path = MODEL_DIR / "training_report.json"
            with open(report_path, "w") as f:
                json.dump(report, f, indent=2, default=float)

            logger.info(f"Saved training report to {report_path}")

    # Export for mobile
    if args.export:
        export_for_mobile(model)

    return 0


if __name__ == "__main__":
    sys.exit(main())
