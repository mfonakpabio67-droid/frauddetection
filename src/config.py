from pathlib import Path
import os


BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / "models"


def _resolve_artifact(env_key: str, candidates) -> Path:
    env_val = os.getenv(env_key)
    if env_val:
        return Path(env_val)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


MODEL_PATH = _resolve_artifact(
    "MODEL_PATH",
    [
        MODELS_DIR / "isolation_forest.joblib",
        BASE_DIR / "fraud_model.pkl",
    ],
)
SCALER_PATH = _resolve_artifact(
    "SCALER_PATH",
    [
        MODELS_DIR / "robust_scaler.joblib",
        BASE_DIR / "scaler.pkl",
    ],
)
METADATA_PATH = Path(os.getenv("METADATA_PATH", MODELS_DIR / "model_metadata.json"))

FLASK_ENV = os.getenv("FLASK_ENV", "development")
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")
RATE_LIMIT = os.getenv("RATE_LIMIT", "60 per minute")

# Vercel's serverless filesystem is read-only except /tmp at runtime.
_default_db_path = Path("/tmp/transactions.db") if os.getenv("VERCEL") else (BASE_DIR / "data" / "transactions.db")
TRANSACTION_DB_PATH = Path(os.getenv("TRANSACTION_DB_PATH", _default_db_path))
