import argparse
import json
from pathlib import Path
from typing import Dict, Tuple

import joblib
import matplotlib.pyplot as plt
import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.ensemble import IsolationForest
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import RobustScaler


BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)


def generate_synthetic_financial_data(
    n_normal: int = 12000,
    n_anomalies: int = 500,
    random_state: int = 42,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Generate synthetic transaction data with:
      1) Transaction_Amount
      2) Distance_From_Home
      3) Time_Since_Last_Transaction
    """
    rng = np.random.default_rng(seed=random_state)

    # Normal behavior distributions
    amount_normal = rng.lognormal(mean=3.7, sigma=0.45, size=n_normal)
    distance_normal = rng.gamma(shape=2.0, scale=2.5, size=n_normal)
    time_delta_normal = rng.exponential(scale=25.0, size=n_normal)

    # Inject anomalies (high amount, large distance, bursty or very sparse timing)
    amount_anom = rng.lognormal(mean=6.0, sigma=0.8, size=n_anomalies)
    distance_anom = rng.gamma(shape=7.0, scale=5.0, size=n_anomalies)
    time_delta_anom = np.concatenate(
        [
            rng.exponential(scale=1.5, size=n_anomalies // 2),
            rng.exponential(scale=240.0, size=n_anomalies - (n_anomalies // 2)),
        ]
    )
    rng.shuffle(time_delta_anom)

    normal = np.column_stack([amount_normal, distance_normal, time_delta_normal])
    anomalies = np.column_stack([amount_anom, distance_anom, time_delta_anom])
    X = np.vstack([normal, anomalies])
    y_synthetic = np.hstack([np.ones(n_normal, dtype=int), -np.ones(n_anomalies, dtype=int)])
    return X, y_synthetic


def tune_isolation_forest(X_scaled: np.ndarray, random_state: int = 42) -> Dict:
    contamination_grid = [0.02, 0.03, 0.04, 0.05, 0.08]
    estimators_grid = [100, 200, 300]
    best = None

    # Proxy objective: higher separation in decision function between predicted inlier/outlier.
    for contamination in contamination_grid:
        for n_estimators in estimators_grid:
            model = IsolationForest(
                n_estimators=n_estimators,
                contamination=contamination,
                random_state=random_state,
                n_jobs=-1,
            )
            model.fit(X_scaled)
            preds = model.predict(X_scaled)
            scores = model.decision_function(X_scaled)

            inlier_scores = scores[preds == 1]
            outlier_scores = scores[preds == -1]
            if len(inlier_scores) == 0 or len(outlier_scores) == 0:
                continue

            gap = float(np.mean(inlier_scores) - np.mean(outlier_scores))
            score = gap
            candidate = {
                "score": score,
                "params": {"contamination": contamination, "n_estimators": n_estimators},
                "model": model,
            }

            if best is None or candidate["score"] > best["score"]:
                best = candidate

    if best is None:
        raise RuntimeError("IsolationForest tuning failed to produce a valid candidate.")

    return best


def tune_dbscan(X_scaled: np.ndarray) -> Dict:
    eps_grid = [0.3, 0.5, 0.7, 0.9, 1.1]
    min_samples_grid = [5, 10, 20, 30]
    best = None

    for eps in eps_grid:
        for min_samples in min_samples_grid:
            model = DBSCAN(eps=eps, min_samples=min_samples)
            labels = model.fit_predict(X_scaled)

            # DBSCAN gives -1 for noise; requires >1 cluster for silhouette
            non_noise_mask = labels != -1
            clustered_labels = labels[non_noise_mask]

            if len(np.unique(clustered_labels)) < 2 or non_noise_mask.sum() < 20:
                continue

            try:
                sil = silhouette_score(X_scaled[non_noise_mask], clustered_labels)
            except ValueError:
                continue

            outlier_ratio = float(np.mean(labels == -1))
            candidate = {
                "score": float(sil),
                "params": {"eps": eps, "min_samples": min_samples},
                "model": model,
                "outlier_ratio": outlier_ratio,
            }

            if best is None or candidate["score"] > best["score"]:
                best = candidate

    return best if best is not None else {
        "score": None,
        "params": None,
        "model": None,
        "outlier_ratio": None,
    }


def save_visualization(X_scaled: np.ndarray, labels: np.ndarray, out_file: Path) -> None:
    plt.figure(figsize=(9, 6))
    normal_mask = labels == 1
    anomaly_mask = labels == -1
    plt.scatter(
        X_scaled[normal_mask, 0],
        X_scaled[normal_mask, 1],
        s=8,
        alpha=0.35,
        label="Normal",
    )
    plt.scatter(
        X_scaled[anomaly_mask, 0],
        X_scaled[anomaly_mask, 1],
        s=16,
        alpha=0.8,
        label="Anomaly",
    )
    plt.title("Isolation Forest Separation (Scaled Feature Space)")
    plt.xlabel("Transaction_Amount (scaled)")
    plt.ylabel("Distance_From_Home (scaled)")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_file, dpi=180)
    plt.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Train unsupervised fraud anomaly models.")
    parser.add_argument(
        "--algorithm",
        choices=["isolation_forest", "dbscan"],
        default="isolation_forest",
        help="Primary algorithm to serialize for API inference.",
    )
    args = parser.parse_args()

    print("Generating synthetic data...")
    X, y_synthetic = generate_synthetic_financial_data()

    print("Applying RobustScaler (median/IQR-based, robust to heavy-tailed financial outliers)...")
    scaler = RobustScaler()
    X_scaled = scaler.fit_transform(X)

    print("Tuning Isolation Forest...")
    iso_best = tune_isolation_forest(X_scaled)
    iso_model = iso_best["model"]
    iso_preds = iso_model.predict(X_scaled)

    print("Tuning DBSCAN benchmark (for comparison)...")
    dbscan_best = tune_dbscan(X_scaled)

    # Choose primary model for deployment
    if args.algorithm == "dbscan":
        # DBSCAN lacks clean predict for out-of-sample points in sklearn.
        # We still allow artifact save for experimentation.
        primary_model = dbscan_best["model"] if dbscan_best["model"] is not None else iso_model
        primary_name = "dbscan" if dbscan_best["model"] is not None else "isolation_forest_fallback"
        deploy_filename = "dbscan.joblib" if dbscan_best["model"] is not None else "isolation_forest.joblib"
    else:
        primary_model = iso_model
        primary_name = "isolation_forest"
        deploy_filename = "isolation_forest.joblib"

    print("Saving artifacts...")
    model_path = MODELS_DIR / deploy_filename
    scaler_path = MODELS_DIR / "robust_scaler.joblib"
    metadata_path = MODELS_DIR / "model_metadata.json"
    chart_path = MODELS_DIR / "anomaly_scatter.png"

    joblib.dump(primary_model, model_path)
    joblib.dump(scaler, scaler_path)

    metadata = {
        "feature_order": [
            "Transaction_Amount",
            "Distance_From_Home",
            "Time_Since_Last_Transaction",
        ],
        "synthetic_data_shape": list(X.shape),
        "synthetic_label_counts": {
            "normal": int(np.sum(y_synthetic == 1)),
            "anomaly": int(np.sum(y_synthetic == -1)),
        },
        "primary_model": primary_name,
        "isolation_forest_best_params": iso_best["params"],
        "isolation_forest_separation_score": round(float(iso_best["score"]), 6),
        "isolation_forest_predicted_outlier_ratio": round(float(np.mean(iso_preds == -1)), 6),
        "dbscan_best_params": dbscan_best.get("params"),
        "dbscan_silhouette_score": dbscan_best.get("score"),
        "dbscan_outlier_ratio": dbscan_best.get("outlier_ratio"),
        "notes": {
            "robust_scaler_reason": "Median/IQR scaling is less sensitive to extreme transaction values.",
            "dbscan_limitations": [
                "No native out-of-sample predict() in sklearn DBSCAN",
                "Operationally weaker for low-latency streaming inference",
            ],
            "anomaly_label_convention": "-1 corresponds to anomaly/outlier in sklearn APIs.",
        },
    }

    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    save_visualization(X_scaled, iso_preds, chart_path)

    print(f"Model saved: {model_path}")
    print(f"Scaler saved: {scaler_path}")
    print(f"Metadata saved: {metadata_path}")
    print(f"Visualization saved: {chart_path}")


if __name__ == "__main__":
    main()

