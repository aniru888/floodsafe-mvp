"""
Step 1: Save MobileNet model as SavedModel format.

This script loads the H5 model and saves it as TensorFlow SavedModel,
which can then be converted to ONNX using tf2onnx CLI.

Usage:
    cd apps/ml-service
    python scripts/save_savedmodel.py
"""

import os
import sys
from pathlib import Path

# Suppress TensorFlow warnings
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import numpy as np


def build_mobilenet_model():
    """Build MobileNet architecture matching Sohail's model."""
    import tensorflow as tf
    from tensorflow.keras.applications import MobileNet
    from tensorflow.keras import layers, Model

    tf.get_logger().setLevel('ERROR')

    base = MobileNet(
        input_shape=(224, 224, 3),
        include_top=False,
        weights=None,
        pooling='avg'
    )

    x = base.output
    output = layers.Dense(2, activation='softmax', name='dense')(x)
    model = Model(inputs=base.input, outputs=output)

    return model


def load_weights_from_h5(model, h5_path: Path) -> int:
    """Load weights from Sohail's H5 file into fresh MobileNet."""
    import h5py

    loaded_count = 0
    with h5py.File(h5_path, 'r') as f:
        weights_group = f['model_weights']
        h5_layer_names = set(weights_group.keys())

        for layer in model.layers:
            if not layer.weights:
                continue

            if layer.name not in h5_layer_names:
                continue

            try:
                layer_weights = weights_group[layer.name][layer.name]
                weight_list = []

                weight_names = list(layer_weights.keys())

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
                print(f"Warning: Could not load weights for {layer.name}: {e}")

    return loaded_count


def main():
    print("=" * 60)
    print("Step 1: Save MobileNet as SavedModel format")
    print("=" * 60)

    h5_path = project_root / "models" / "sohail_flood_model.h5"
    savedmodel_path = project_root / "models" / "flood_classifier_savedmodel"

    print(f"\n1. Loading H5 model from: {h5_path}")

    # Build and load model
    print("2. Building MobileNet architecture...")
    model = build_mobilenet_model()

    print("3. Loading weights from H5...")
    loaded_count = load_weights_from_h5(model, h5_path)
    print(f"   Loaded weights for {loaded_count} layers")

    # Verify model
    print("4. Verifying model inference...")
    test_input = np.random.randn(1, 224, 224, 3).astype(np.float32)
    test_output = model.predict(test_input, verbose=0)
    print(f"   Test output: [flood={test_output[0][0]:.4f}, no_flood={test_output[0][1]:.4f}]")

    # Save as SavedModel (Keras 3 uses model.export() for TF SavedModel format)
    print(f"\n5. Saving as SavedModel to: {savedmodel_path}")
    model.export(str(savedmodel_path))

    print(f"\n6. SavedModel saved successfully!")
    print(f"   Path: {savedmodel_path}")

    print("\nNext step: Convert to ONNX using tf2onnx CLI:")
    print(f"  python -m tf2onnx.convert --saved-model {savedmodel_path} --output {project_root / 'models' / 'flood_classifier.onnx'} --opset 13")


if __name__ == "__main__":
    main()
