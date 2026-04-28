from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional
import json

import joblib
import numpy as np

from src.services.risk_service import RiskService


@dataclass
class LoadedArtifacts:
    model: object
    scaler: object
    metadata: Dict


class ModelService:
    """Handles model/scaler loading and real-time anomaly scoring."""

    def __init__(
        self,
        model_path: Path,
        scaler_path: Path,
        metadata_path: Optional[Path] = None,
    ) -> None:
        self.model_path = model_path
        self.scaler_path = scaler_path
        self.metadata_path = metadata_path
        self.risk_service = RiskService()
        self.artifacts = self._load_artifacts()

    def _load_artifacts(self) -> LoadedArtifacts:
        if not self.model_path.exists():
            raise FileNotFoundError(f"Model file not found: {self.model_path}")
        if not self.scaler_path.exists():
            raise FileNotFoundError(f"Scaler file not found: {self.scaler_path}")

        model = joblib.load(self.model_path)
        scaler = joblib.load(self.scaler_path)
        metadata = {}

        if self.metadata_path and self.metadata_path.exists():
            metadata = json.loads(self.metadata_path.read_text(encoding="utf-8"))

        return LoadedArtifacts(model=model, scaler=scaler, metadata=metadata)

    def predict(self, amount: float, distance: float, time_delta: float) -> Dict:
        raw = np.array([[amount, distance, time_delta]], dtype=np.float64)
        scaled = self.artifacts.scaler.transform(raw)

        prediction = int(self.artifacts.model.predict(scaled)[0])  # 1 or -1
        decision_score = float(self.artifacts.model.decision_function(scaled)[0])
        risk_score = self.risk_service.normalize_anomaly_score(decision_score)
        risk_level = self.risk_service.risk_level(risk_score)

        return {
            "is_fraudulent": prediction == -1,
            "prediction_label": prediction,
            "risk_score": round(risk_score, 4),
            "risk_level": risk_level,
            "decision_score": round(decision_score, 6),
            "explanation": self.risk_service.explain(scaled),
        }

