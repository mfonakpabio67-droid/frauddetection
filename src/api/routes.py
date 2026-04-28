from flask import Blueprint, current_app, jsonify, request

from src.utils.validators import validate_transaction_payload


api_blueprint = Blueprint("api", __name__, url_prefix="/api")


@api_blueprint.get("/health")
def health():
    startup_errors = current_app.config.get("STARTUP_ERRORS", [])
    if startup_errors:
        return jsonify({"status": "degraded", "startup_errors": startup_errors}), 503
    return jsonify({"status": "ok"})


@api_blueprint.get("/metrics")
def metrics():
    txn_log = current_app.config["TRANSACTION_LOG"]
    if txn_log is None:
        startup_errors = current_app.config.get("STARTUP_ERRORS", [])
        return (
            jsonify(
                {
                    "error": "Transaction log unavailable.",
                    "startup_errors": startup_errors,
                }
            ),
            503,
        )
    return jsonify(txn_log.metrics())


@api_blueprint.get("/transactions/recent")
def recent_transactions():
    txn_log = current_app.config["TRANSACTION_LOG"]
    if txn_log is None:
        startup_errors = current_app.config.get("STARTUP_ERRORS", [])
        return (
            jsonify(
                {
                    "error": "Transaction log unavailable.",
                    "startup_errors": startup_errors,
                }
            ),
            503,
        )
    limit_raw = request.args.get("limit", default="20")
    try:
        limit = max(1, min(int(limit_raw), 200))
    except ValueError:
        return jsonify({"error": "Query parameter 'limit' must be an integer."}), 400
    return jsonify({"transactions": txn_log.recent(limit=limit)})


@api_blueprint.post("/verify_transaction")
def verify_transaction():
    try:
        payload = request.get_json(silent=True)
        data = validate_transaction_payload(payload)
    except ValueError as exc:
        current_app.logger.warning("Invalid payload: %s", exc)
        return jsonify({"error": str(exc)}), 400

    model_service = current_app.config["MODEL_SERVICE"]
    txn_log = current_app.config["TRANSACTION_LOG"]
    if model_service is None:
        startup_errors = current_app.config.get("STARTUP_ERRORS", [])
        return (
            jsonify(
                {
                    "error": "Model unavailable.",
                    "startup_errors": startup_errors,
                }
            ),
            503,
        )

    try:
        result = model_service.predict(
            amount=data["amount"],
            distance=data["distance"],
            time_delta=data["time_delta"],
        )
    except Exception as exc:  # Defensive catch for production stability
        current_app.logger.exception("Inference failure: %s", exc)
        return jsonify({"error": "Internal model inference error."}), 500

    txn_record = {
        "amount": data["amount"],
        "distance": data["distance"],
        "time_delta": data["time_delta"],
        "is_fraudulent": result["is_fraudulent"],
        "risk_level": result["risk_level"],
        "risk_score": result["risk_score"],
    }
    if txn_log is not None:
        txn_log.add(txn_record)

    response = {
        "is_fraudulent": result["is_fraudulent"],
        "risk_level": result["risk_level"],
        "risk_score": result["risk_score"],
        "prediction_label": result["prediction_label"],
        "explanation": result["explanation"],
    }
    return jsonify(response), 200
