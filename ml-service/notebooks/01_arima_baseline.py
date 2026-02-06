"""
ARIMA Baseline Model - Example Usage

This script demonstrates how to use the ARIMA flood model for:
1. Time series forecasting
2. Model selection (order tuning)
3. Probability estimation
4. Model persistence

Run: python notebooks/01_arima_baseline.py
"""

import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from models import ARIMAFloodModel


def generate_synthetic_flood_data(n_samples=200, seed=42):
    """
    Generate synthetic flood-like time series data.

    Simulates:
    - Seasonal pattern (monsoon)
    - Upward trend (climate change)
    - Random fluctuations
    - Occasional spikes (flood events)
    """
    np.random.seed(seed)
    t = np.arange(n_samples)

    # Components
    trend = 0.05 * t  # Gradual increase
    seasonal = 10 * np.sin(2 * np.pi * t / 30)  # Monthly cycle
    noise = np.random.normal(0, 2, n_samples)

    # Occasional flood spikes
    flood_events = np.zeros(n_samples)
    flood_indices = np.random.choice(n_samples, size=5, replace=False)
    flood_events[flood_indices] = np.random.uniform(15, 25, size=5)

    # Combine (base water level at 50)
    y = 50 + trend + seasonal + noise + flood_events

    return y


def example_basic_forecast():
    """Example 1: Basic forecasting."""
    print("=" * 60)
    print("EXAMPLE 1: Basic ARIMA Forecast")
    print("=" * 60)

    # Generate data
    y = generate_synthetic_flood_data(n_samples=150)
    print(f"Generated {len(y)} samples")
    print(f"Mean: {y.mean():.2f}, Std: {y.std():.2f}, Max: {y.max():.2f}")

    # Train/test split
    train_size = 120
    y_train = y[:train_size]
    y_test = y[train_size:]

    # Initialize and train
    model = ARIMAFloodModel(order=(5, 1, 0), threshold=60.0)
    print(f"\nModel: {model}")

    print("\nFitting model...")
    model.fit(X=None, y=y_train, check_stationarity=True)

    # Check stationarity result
    if 'stationarity_test' in model.training_history:
        st = model.training_history['stationarity_test']
        print(f"Stationarity test p-value: {st.get('pvalue', 'N/A'):.4f}")
        print(f"Is stationary: {st.get('is_stationary', 'N/A')}")

    print(f"AIC: {model.training_history['aic']:.2f}")
    print(f"BIC: {model.training_history['bic']:.2f}")

    # Forecast
    steps = len(y_test)
    predictions = model.predict(steps=steps)
    probabilities = model.predict_proba(steps=steps)

    print(f"\nForecast for next {steps} steps:")
    print(f"Predictions: {predictions[:5]}...")
    print(f"Probabilities: {probabilities[:5]}...")

    # Calculate error
    mae = np.mean(np.abs(y_test - predictions))
    rmse = np.sqrt(np.mean((y_test - predictions) ** 2))

    print(f"\nError metrics:")
    print(f"MAE: {mae:.2f}")
    print(f"RMSE: {rmse:.2f}")

    return model, y_train, y_test, predictions


def example_seasonal_arima():
    """Example 2: SARIMA for seasonal data."""
    print("\n" + "=" * 60)
    print("EXAMPLE 2: Seasonal ARIMA (SARIMA)")
    print("=" * 60)

    # Generate longer series for seasonality
    y = generate_synthetic_flood_data(n_samples=250)
    y_train = y[:200]

    # SARIMA with monthly seasonality
    model = ARIMAFloodModel(
        order=(5, 1, 0),
        seasonal_order=(1, 1, 1, 30),  # 30-day cycle
        threshold=60.0
    )

    print(f"Model: {model}")
    print("\nFitting SARIMA...")
    model.fit(X=None, y=y_train, check_stationarity=False)

    print(f"AIC: {model.training_history['aic']:.2f}")

    # Long-term forecast
    predictions = model.predict(steps=50)
    print(f"\nForecasted next 50 steps (mean): {predictions.mean():.2f}")

    return model


def example_model_selection():
    """Example 3: Model order selection."""
    print("\n" + "=" * 60)
    print("EXAMPLE 3: Model Selection (Grid Search)")
    print("=" * 60)

    y = generate_synthetic_flood_data(n_samples=150)[:120]

    # Grid search
    p_values = [1, 3, 5]
    d_values = [0, 1]
    q_values = [0, 1]

    results = []

    print("\nSearching for best order...")
    print(f"{'Order':<15} {'AIC':<10} {'BIC':<10} {'Status'}")
    print("-" * 50)

    for p in p_values:
        for d in d_values:
            for q in q_values:
                try:
                    model = ARIMAFloodModel(order=(p, d, q))
                    model.fit(X=None, y=y, check_stationarity=False)

                    aic = model.training_history['aic']
                    bic = model.training_history['bic']

                    results.append({
                        'order': (p, d, q),
                        'aic': aic,
                        'bic': bic,
                    })

                    print(f"{str((p,d,q)):<15} {aic:<10.2f} {bic:<10.2f} OK")

                except Exception as e:
                    print(f"{str((p,d,q)):<15} {'N/A':<10} {'N/A':<10} FAIL")

    # Find best
    best = min(results, key=lambda x: x['aic'])
    print(f"\nBest order by AIC: {best['order']} (AIC={best['aic']:.2f})")

    return best['order']


def example_save_load():
    """Example 4: Model persistence."""
    print("\n" + "=" * 60)
    print("EXAMPLE 4: Save and Load Model")
    print("=" * 60)

    y = generate_synthetic_flood_data(n_samples=100)

    # Train model
    model = ARIMAFloodModel(order=(5, 1, 0))
    model.fit(X=None, y=y)

    # Make prediction
    pred_before = model.predict(steps=7)
    print(f"Prediction before save: {pred_before[:3]}")

    # Save
    save_dir = Path(__file__).parent.parent / 'models' / 'saved' / 'arima_test'
    save_dir.mkdir(parents=True, exist_ok=True)

    model.save(save_dir)
    print(f"\nModel saved to: {save_dir}")

    # Load
    model_loaded = ARIMAFloodModel()
    model_loaded.load(save_dir)
    print(f"Model loaded: {model_loaded}")

    # Verify prediction matches
    pred_after = model_loaded.predict(steps=7)
    print(f"Prediction after load: {pred_after[:3]}")

    # Check match
    if np.allclose(pred_before, pred_after):
        print("\nVerification: PASS (predictions match)")
    else:
        print("\nVerification: FAIL (predictions differ)")


def main():
    """Run all examples."""
    print("ARIMA Flood Model - Example Demonstrations")
    print()

    # Example 1: Basic
    model1, y_train, y_test, predictions = example_basic_forecast()

    # Example 2: Seasonal
    model2 = example_seasonal_arima()

    # Example 3: Model selection
    best_order = example_model_selection()

    # Example 4: Persistence
    example_save_load()

    print("\n" + "=" * 60)
    print("All examples completed successfully!")
    print("=" * 60)

    # Optional: Plot results from Example 1
    try:
        plt.figure(figsize=(12, 6))

        plt.subplot(2, 1, 1)
        plt.plot(y_train, label='Training Data', color='blue', alpha=0.7)
        plt.plot(range(len(y_train), len(y_train) + len(y_test)),
                 y_test, label='Actual', color='green', alpha=0.7)
        plt.plot(range(len(y_train), len(y_train) + len(predictions)),
                 predictions, label='Forecast', color='red', linestyle='--')
        plt.xlabel('Time')
        plt.ylabel('Water Level')
        plt.title('ARIMA Flood Forecast')
        plt.legend()
        plt.grid(True, alpha=0.3)

        plt.subplot(2, 1, 2)
        probs = model1.predict_proba(steps=len(y_test))
        plt.plot(range(len(y_train), len(y_train) + len(probs)),
                 probs, label='Flood Probability', color='red', linewidth=2)
        plt.axhline(y=0.5, color='orange', linestyle='--', label='50% Threshold')
        plt.xlabel('Time')
        plt.ylabel('Probability')
        plt.title('Flood Probability Forecast')
        plt.legend()
        plt.grid(True, alpha=0.3)
        plt.ylim(0, 1)

        plt.tight_layout()

        # Save plot
        plot_path = Path(__file__).parent / 'arima_example_plot.png'
        plt.savefig(plot_path, dpi=150)
        print(f"\nPlot saved to: {plot_path}")

    except Exception as e:
        print(f"\nNote: Plotting skipped ({e})")


if __name__ == "__main__":
    main()
