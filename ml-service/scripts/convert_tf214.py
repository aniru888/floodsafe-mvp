"""
Convert MobileNet flood classifier to TFLite using TensorFlow 2.14.x

CRITICAL: This script MUST be run with TensorFlow 2.14.x to produce
opcodes compatible with tflite-runtime 2.14.0.

TF 2.17+ produces FULLY_CONNECTED opcode v12 which is NOT supported
by tflite-runtime 2.14.0 (the latest version on PyPI).

Usage (in Docker):
    docker build -f scripts/Dockerfile.convert -t tf214-convert .
    docker run -v ${PWD}/models:/app/models -v ${PWD}/scripts:/app/scripts tf214-convert
"""

import os
import sys
from pathlib import Path

# Suppress TensorFlow warnings
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

import numpy as np


def verify_tensorflow_version():
    """Verify TensorFlow version is 2.14.x for opcode compatibility."""
    import tensorflow as tf

    version = tf.__version__
    major_minor = '.'.join(version.split('.')[:2])

    print(f"TensorFlow version: {version}")

    if not version.startswith('2.14'):
        print(f"\nERROR: TensorFlow {version} detected!")
        print("This script MUST be run with TensorFlow 2.14.x")
        print("TF 2.17+ produces FULLY_CONNECTED opcode v12 which is NOT supported")
        print("by tflite-runtime 2.14.0 (the latest version on PyPI).")
        print("\nRun this in the Docker container:")
        print("  docker build -f scripts/Dockerfile.convert -t tf214-convert .")
        print("  docker run -v ${PWD}/models:/app/models -v ${PWD}/scripts:/app/scripts tf214-convert")
        sys.exit(1)

    print(f"[OK] TensorFlow 2.14.x confirmed - opcodes will be compatible")
    return version


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


def verify_tflite_model(tflite_path: Path, test_input: np.ndarray, original_output: np.ndarray):
    """Verify TFLite model works and produces similar output."""
    import tensorflow as tf

    print("\n7. Verifying TFLite model...")

    interpreter = tf.lite.Interpreter(model_path=str(tflite_path))
    interpreter.allocate_tensors()

    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()

    print(f"   Input: {input_details[0]['shape']}, dtype={input_details[0]['dtype']}")
    print(f"   Output: {output_details[0]['shape']}, dtype={output_details[0]['dtype']}")

    # Run test inference
    interpreter.set_tensor(input_details[0]['index'], test_input)
    interpreter.invoke()
    tflite_output = interpreter.get_tensor(output_details[0]['index'])

    print(f"   TFLite output: [flood={tflite_output[0][0]:.4f}, no_flood={tflite_output[0][1]:.4f}]")

    # Compare outputs
    diff = np.abs(original_output - tflite_output).max()
    print(f"   Max diff vs original: {diff:.6f}")

    if diff > 0.01:
        print(f"\nWARNING: Output difference is significant ({diff:.6f} > 0.01)")
        print("Model accuracy may be affected!")
    else:
        print(f"   [OK] Output matches original (diff < 0.01)")

    return diff


def main():
    import tensorflow as tf

    print("=" * 60)
    print("Convert MobileNet to TFLite (TF 2.14.x)")
    print("=" * 60)

    # CRITICAL: Verify TensorFlow version first
    tf_version = verify_tensorflow_version()

    # Paths - handle both local and Docker execution
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    h5_path = project_root / "models" / "sohail_flood_model.h5"
    tflite_path = project_root / "models" / "flood_classifier.tflite"

    # Check if running in Docker (mounted paths)
    if not h5_path.exists():
        h5_path = Path("/app/models/sohail_flood_model.h5")
        tflite_path = Path("/app/models/flood_classifier.tflite")

    if not h5_path.exists():
        print(f"\nERROR: Source model not found at {h5_path}")
        print("Make sure the models directory is mounted correctly.")
        sys.exit(1)

    print(f"\n1. Source H5 model: {h5_path}")
    print(f"   Output TFLite: {tflite_path}")

    # Build and load model
    print("\n2. Building MobileNet architecture...")
    model = build_mobilenet_model()

    print("3. Loading weights from H5...")
    loaded_count = load_weights_from_h5(model, h5_path)
    print(f"   Loaded weights for {loaded_count} layers")

    # Verify model
    print("\n4. Verifying model inference...")
    test_input = np.random.randn(1, 224, 224, 3).astype(np.float32)
    test_output = model.predict(test_input, verbose=0)
    print(f"   Test output: [flood={test_output[0][0]:.4f}, no_flood={test_output[0][1]:.4f}]")

    # Convert to TFLite
    print(f"\n5. Converting to TFLite with TF {tf_version}...")
    converter = tf.lite.TFLiteConverter.from_keras_model(model)

    # Optimize for size and speed
    converter.optimizations = [tf.lite.Optimize.DEFAULT]

    tflite_model = converter.convert()

    # Save TFLite model
    print(f"\n6. Saving TFLite model to: {tflite_path}")
    with open(tflite_path, 'wb') as f:
        f.write(tflite_model)

    # Get file size
    size_mb = tflite_path.stat().st_size / 1024 / 1024
    print(f"   Model size: {size_mb:.2f} MB")

    # Verify TFLite model
    diff = verify_tflite_model(tflite_path, test_input, test_output)

    print("\n" + "=" * 60)
    print("TFLite conversion successful!")
    print(f"TensorFlow version: {tf_version}")
    print(f"Model saved to: {tflite_path}")
    print(f"Model size: {size_mb:.2f} MB")
    print(f"Output accuracy diff: {diff:.6f}")
    print("=" * 60)
    print("\nThis model is compatible with tflite-runtime 2.14.0")


if __name__ == "__main__":
    main()
