from typing import Dict, List
import numpy as np


class RiskService:
    """Convert model outputs into risk score, levels, and feature-level explanations."""

    feature_names = [
        "Transaction_Amount",
        "Distance_From_Home",
        "Time_Since_Last_Transaction",
    ]

    def normalize_anomaly_score(self, decision_score: float) -> float:
        """
        Convert IsolationForest decision_function output to risk score [0,1].

        decision_function:
            > 0 => more normal
            < 0 => more anomalous
        We invert and squash with logistic to get intuitive risk scale.
        """
        scaled = -4.0 * decision_score
        risk = 1.0 / (1.0 + np.exp(-scaled))
        return float(np.clip(risk, 0.0, 1.0))

    def risk_level(self, risk_score: float) -> str:
        if risk_score >= 0.9:
            return "CRITICAL"
        if risk_score >= 0.7:
            return "HIGH"
        if risk_score >= 0.4:
            return "MEDIUM"
        return "LOW"

    def explain(
        self,
        scaled_row: np.ndarray,
        threshold_sigma: float = 2.0,
        max_reasons: int = 2,
    ) -> Dict[str, List[str]]:
        """
        Explain risk with robust z-score style interpretation in scaled space.
        After RobustScaler, values around 0 are near median, high magnitude => unusual.
        """
        values = np.abs(scaled_row.flatten())
        ranked_idx = np.argsort(values)[::-1]
        reasons: List[str] = []

        for idx in ranked_idx:
            if values[idx] < threshold_sigma:
                continue
            feature = self.feature_names[idx]
            direction = "above" if scaled_row.flatten()[idx] > 0 else "below"
            reasons.append(f"{feature} {direction} typical range")
            if len(reasons) >= max_reasons:
                break

        if not reasons:
            reasons.append("No extreme feature deviation detected")

        return {"top_risk_factors": reasons}

