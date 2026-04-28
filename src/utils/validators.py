from typing import Dict


REQUIRED_KEYS = ("amount", "distance", "time_delta")


def validate_transaction_payload(payload: Dict) -> Dict[str, float]:
    """Validate and normalize transaction payload for inference."""
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object.")

    missing = [key for key in REQUIRED_KEYS if key not in payload]
    if missing:
        raise ValueError(f"Missing required field(s): {', '.join(missing)}")

    normalized = {}
    for key in REQUIRED_KEYS:
        value = payload[key]
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"Field '{key}' must be numeric.") from None

        if numeric < 0:
            raise ValueError(f"Field '{key}' cannot be negative.")

        normalized[key] = numeric

    return normalized

