#!/usr/bin/env python3
"""
Test Sohail Ahmed Khan's pretrained flood detection model on Indian images.

Model: MobileNetV1 trained on roadway flood images
Source: https://github.com/sohailahmedkhan/Flood-Detection-from-Images-using-Deep-Learning
"""

import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # Suppress TF warnings

from pathlib import Path
import numpy as np
from PIL import Image
import h5py

# Set up paths
ML_SERVICE_DIR = Path(__file__).parent.parent
DATA_DIR = ML_SERVICE_DIR / "data" / "indian_test"
MODEL_PATH = ML_SERVICE_DIR / "models" / "sohail_flood_model.h5"


def load_weights_only():
    """
    Load weights from Sohail's h5 file into a fresh MobileNet architecture.
    This bypasses Keras 3.x serialization incompatibility.
    """
    import tensorflow as tf
    from tensorflow.keras.applications import MobileNet
    from tensorflow.keras import layers, Model

    # Create MobileNet base with same config as Sohail's model
    # Input: 224x224x3, output: 1024-dim features before classification
    base = MobileNet(
        input_shape=(224, 224, 3),
        include_top=False,
        weights=None,  # Don't load ImageNet weights
        pooling='avg'  # Global average pooling
    )

    # Add classification head (2 classes: flood, no_flood)
    x = base.output
    output = layers.Dense(2, activation='softmax', name='dense')(x)
    model = Model(inputs=base.input, outputs=output)

    # Load weights from h5 file
    print(f"Loading weights from: {MODEL_PATH}")
    loaded_count = 0
    with h5py.File(MODEL_PATH, 'r') as f:
        weights_group = f['model_weights']
        h5_layer_names = set(weights_group.keys())

        for layer in model.layers:
            # Skip layers without weights
            if not layer.weights:
                continue

            # Check if layer exists in h5 file
            if layer.name not in h5_layer_names:
                continue

            try:
                layer_weights = weights_group[layer.name][layer.name]
                weight_list = []

                # Get weight names - Keras expects: kernel, bias for Dense; gamma, beta, mean, var for BN
                weight_names = list(layer_weights.keys())
                # Sort by expected Keras order
                def weight_order(name):
                    if 'kernel' in name or 'depthwise_kernel' in name:
                        return 0
                    elif 'gamma' in name:
                        return 1
                    elif 'beta' in name:
                        return 2
                    elif 'moving_mean' in name:
                        return 3
                    elif 'moving_variance' in name:
                        return 4
                    elif 'bias' in name:
                        return 5
                    return 99

                for wname in sorted(weight_names, key=weight_order):
                    weight_list.append(np.array(layer_weights[wname]))

                if weight_list:
                    layer.set_weights(weight_list)
                    loaded_count += 1
            except Exception as e:
                print(f"  Warning: Could not load weights for {layer.name}: {e}")

    print(f"Loaded weights for {loaded_count} layers")
    print(f"Input shape: {model.input_shape}")
    print(f"Output shape: {model.output_shape}")

    return model


def preprocess_image(image_path: Path) -> np.ndarray:
    """
    Preprocess image for MobileNet input.
    Sohail's model uses standard MobileNet preprocessing (scale to [-1, 1]).
    """
    img = Image.open(image_path).convert('RGB')
    img = img.resize((224, 224), Image.BILINEAR)
    arr = np.array(img, dtype=np.float32)

    # MobileNet preprocessing: scale to [-1, 1]
    arr = (arr / 127.5) - 1.0

    return np.expand_dims(arr, axis=0)


def run_inference(model, image_dir: Path, expected_class: int) -> dict:
    """
    Run inference on all images in a directory.

    Args:
        model: Keras model
        image_dir: Directory containing images
        expected_class: 0 for no_flood, 1 for flood

    Returns:
        dict with predictions and accuracy
    """
    results = []

    for img_path in sorted(image_dir.glob("*.jpg")):
        img = preprocess_image(img_path)
        pred = model.predict(img, verbose=0)[0]

        # Sohail's model: [flood_prob, no_flood_prob] - REVERSED from our assumption!
        # Class 0 = flood, Class 1 = no_flood
        raw_class = np.argmax(pred)
        # Convert: Sohail's class 0 (flood) → our class 1, Sohail's class 1 (no_flood) → our class 0
        predicted_class = 1 - raw_class  # Flip the class
        confidence = pred[raw_class]

        is_correct = predicted_class == expected_class

        results.append({
            'image': img_path.name,
            'predicted': 'flood' if predicted_class == 1 else 'no_flood',
            'expected': 'flood' if expected_class == 1 else 'no_flood',
            'confidence': float(confidence),
            'correct': is_correct,
        })

        status = "[OK]" if is_correct else "[X]"
        print(f"  {status} {img_path.name}: {results[-1]['predicted']} ({confidence:.2%})")

    accuracy = sum(r['correct'] for r in results) / len(results) if results else 0
    return {'results': results, 'accuracy': accuracy}


def main():
    print("=" * 60)
    print("SOHAIL'S PRETRAINED FLOOD MODEL - INDIAN IMAGE TEST")
    print("=" * 60)

    # Check paths
    if not MODEL_PATH.exists():
        print(f"ERROR: Model not found at {MODEL_PATH}")
        return

    flood_dir = DATA_DIR / "flood"
    no_flood_dir = DATA_DIR / "no_flood"

    if not flood_dir.exists() or not no_flood_dir.exists():
        print(f"ERROR: Test images not found at {DATA_DIR}")
        return

    # Load model
    print("\n--- Loading Model ---")
    model = load_weights_only()

    # Test on flood images (expected class = 1)
    print("\n--- Testing on FLOOD images ---")
    flood_results = run_inference(model, flood_dir, expected_class=1)

    # Test on no_flood images (expected class = 0)
    print("\n--- Testing on NO_FLOOD images ---")
    no_flood_results = run_inference(model, no_flood_dir, expected_class=0)

    # Calculate overall metrics
    all_results = flood_results['results'] + no_flood_results['results']
    overall_accuracy = sum(r['correct'] for r in all_results) / len(all_results)

    # Print summary
    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    print(f"Flood images:    {flood_results['accuracy']:.1%} ({sum(r['correct'] for r in flood_results['results'])}/{len(flood_results['results'])})")
    print(f"No-flood images: {no_flood_results['accuracy']:.1%} ({sum(r['correct'] for r in no_flood_results['results'])}/{len(no_flood_results['results'])})")
    print(f"Overall:         {overall_accuracy:.1%} ({sum(r['correct'] for r in all_results)}/{len(all_results)})")
    print("=" * 60)

    # Decision based on accuracy
    print("\n--- DECISION ---")
    if overall_accuracy >= 0.80:
        print(f"[PASS] Accuracy {overall_accuracy:.1%} >= 80% - Sohail's model works for India!")
        print("  Recommendation: Use this model, no need for custom training.")
    elif overall_accuracy >= 0.70:
        print(f"[WARN] Accuracy {overall_accuracy:.1%} - Moderate performance")
        print("  Recommendation: Consider fine-tuning with Indian data.")
    else:
        print(f"[FAIL] Accuracy {overall_accuracy:.1%} < 70% - Model doesn't generalize well")
        print("  Recommendation: Proceed to Step 2 - Train on Kaggle data.")

    return overall_accuracy


if __name__ == "__main__":
    main()
