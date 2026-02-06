"""
Convert TensorFlow/Keras MobileNet Flood Classifier to ONNX format.

This script converts the Sohail Ahmed Khan's pretrained MobileNet model
from H5 (Keras) format to ONNX for lightweight deployment.

Benefits of ONNX:
- ONNX Runtime is ~50MB vs TensorFlow's ~500MB
- Faster inference for production
- No TensorFlow dependency in production

Usage:
    cd apps/ml-service
    pip install tensorflow tf2onnx onnx
    python scripts/convert_to_onnx.py

Output:
    models/flood_classifier.onnx (~27MB)
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def build_mobilenet_model():
    """Build MobileNet architecture matching Sohail's model."""
    import tensorflow as tf
    from tensorflow.keras.applications import MobileNet
    from tensorflow.keras import layers, Model

    # Suppress TF warnings
    tf.get_logger().setLevel('ERROR')
    os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

    # Create MobileNet base (same as Sohail's architecture)
    base = MobileNet(
        input_shape=(224, 224, 3),
        include_top=False,
        weights=None,
        pooling='avg'
    )

    # Add classification head (2 classes: flood, no_flood)
    x = base.output
    output = layers.Dense(2, activation='softmax', name='dense')(x)
    model = Model(inputs=base.input, outputs=output)

    return model


def load_weights_from_h5(model, h5_path: Path) -> int:
    """
    Load weights from Sohail's H5 file into fresh MobileNet.

    Keras 3.x has serialization incompatibility with older H5 files,
    so we load weights manually layer by layer.
    """
    import h5py
    import numpy as np

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


def convert_to_onnx(h5_path: str, onnx_path: str):
    """
    Convert Keras H5 model to ONNX format.

    Args:
        h5_path: Path to input H5 model
        onnx_path: Path for output ONNX model
    """
    import tensorflow as tf
    import tf2onnx
    import onnx

    print("=" * 60)
    print("FloodSafe ML: Converting MobileNet to ONNX")
    print("=" * 60)

    # Check input exists
    h5_path = Path(h5_path)
    if not h5_path.exists():
        raise FileNotFoundError(f"H5 model not found: {h5_path}")

    print(f"\n1. Loading Keras model from: {h5_path}")
    print(f"   File size: {h5_path.stat().st_size / 1024 / 1024:.1f} MB")

    # Build model architecture
    print("\n2. Building MobileNet architecture...")
    model = build_mobilenet_model()
    print(f"   Input shape: {model.input_shape}")
    print(f"   Output shape: {model.output_shape}")

    # Load weights
    print("\n3. Loading weights from H5...")
    loaded_count = load_weights_from_h5(model, h5_path)
    print(f"   Loaded weights for {loaded_count} layers")

    # Verify model works
    print("\n4. Verifying model inference...")
    import numpy as np
    test_input = np.random.randn(1, 224, 224, 3).astype(np.float32)
    test_output = model.predict(test_input, verbose=0)
    print(f"   Test output shape: {test_output.shape}")
    print(f"   Test output: [flood={test_output[0][0]:.4f}, no_flood={test_output[0][1]:.4f}]")

    # Convert to ONNX
    print("\n5. Converting to ONNX...")
    input_signature = [tf.TensorSpec(model.input_shape, tf.float32, name='input')]

    onnx_model, _ = tf2onnx.convert.from_keras(
        model,
        input_signature=input_signature,
        opset=13,
        output_path=None  # Don't save yet, we'll do it manually
    )

    # Save ONNX model
    onnx_path = Path(onnx_path)
    onnx_path.parent.mkdir(parents=True, exist_ok=True)
    onnx.save(onnx_model, str(onnx_path))

    print(f"\n6. ONNX model saved to: {onnx_path}")
    print(f"   File size: {onnx_path.stat().st_size / 1024 / 1024:.1f} MB")

    # Verify ONNX model
    print("\n7. Verifying ONNX model...")
    import onnxruntime as ort

    session = ort.InferenceSession(str(onnx_path))
    input_name = session.get_inputs()[0].name
    onnx_output = session.run(None, {input_name: test_input})

    print(f"   ONNX output shape: {onnx_output[0].shape}")
    print(f"   ONNX output: [flood={onnx_output[0][0][0]:.4f}, no_flood={onnx_output[0][0][1]:.4f}]")

    # Compare outputs
    diff = np.abs(test_output - onnx_output[0]).max()
    print(f"   Max difference from Keras: {diff:.6f}")

    if diff < 0.001:
        print("\n   CONVERSION SUCCESSFUL!")
    else:
        print(f"\n   WARNING: Output difference is significant ({diff})")

    print("\n" + "=" * 60)
    print("Conversion complete!")
    print(f"  Input: {h5_path} ({h5_path.stat().st_size / 1024 / 1024:.1f} MB)")
    print(f"  Output: {onnx_path} ({onnx_path.stat().st_size / 1024 / 1024:.1f} MB)")
    print("=" * 60)

    return str(onnx_path)


if __name__ == "__main__":
    # Default paths
    h5_model = project_root / "models" / "sohail_flood_model.h5"
    onnx_model = project_root / "models" / "flood_classifier.onnx"

    # Allow override via command line
    if len(sys.argv) > 1:
        h5_model = Path(sys.argv[1])
    if len(sys.argv) > 2:
        onnx_model = Path(sys.argv[2])

    convert_to_onnx(str(h5_model), str(onnx_model))
