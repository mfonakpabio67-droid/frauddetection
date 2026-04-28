import logging
import os
from pathlib import Path

from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from src.api.routes import api_blueprint
from src.config import (
    CORS_ORIGINS,
    FLASK_ENV,
    METADATA_PATH,
    MODEL_PATH,
    RATE_LIMIT,
    SCALER_PATH,
    TRANSACTION_DB_PATH,
)
from src.services.model_service import ModelService
from src.services.transaction_log import TransactionLog


def configure_logging(app: Flask) -> None:
    level = logging.DEBUG if FLASK_ENV == "development" else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    app.logger.setLevel(level)


def create_app() -> Flask:
    app = Flask(__name__, static_folder="frontend", static_url_path="")
    app.config["JSON_SORT_KEYS"] = False

    configure_logging(app)
    CORS(app, resources={r"/api/*": {"origins": CORS_ORIGINS}})

    Limiter(
        key_func=get_remote_address,
        app=app,
        default_limits=[RATE_LIMIT],
        storage_uri="memory://",
    )

    model_service = None
    transaction_log = None
    startup_errors = []

    try:
        model_service = ModelService(
            model_path=MODEL_PATH,
            scaler_path=SCALER_PATH,
            metadata_path=METADATA_PATH,
        )
    except Exception as exc:
        startup_errors.append(f"MODEL_INIT_FAILED: {exc}")
        app.logger.exception("Model service initialization failed: %s", exc)

    try:
        transaction_log = TransactionLog(db_path=TRANSACTION_DB_PATH)
    except Exception as exc:
        startup_errors.append(f"TXN_LOG_INIT_FAILED: {exc}")
        app.logger.exception("Transaction log initialization failed: %s", exc)

    app.config["MODEL_SERVICE"] = model_service
    app.config["TRANSACTION_LOG"] = transaction_log
    app.config["STARTUP_ERRORS"] = startup_errors

    app.register_blueprint(api_blueprint)

    @app.errorhandler(404)
    def not_found(_):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(429)
    def rate_limited(_):
        return jsonify({"error": "Rate limit exceeded"}), 429

    frontend_dir = Path(app.root_path) / "frontend"

    @app.get("/")
    def serve_frontend_root():
        return send_from_directory(frontend_dir, "index.html")

    @app.get("/<path:path>")
    def serve_frontend_assets(path: str):
        requested = frontend_dir / path
        if requested.exists() and requested.is_file():
            return send_from_directory(frontend_dir, path)
        return send_from_directory(frontend_dir, "index.html")

    app.logger.info(
        "API booted. Model=%s Scaler=%s TxnDB=%s",
        MODEL_PATH,
        SCALER_PATH,
        TRANSACTION_DB_PATH,
    )
    if startup_errors:
        app.logger.error("Startup completed with errors: %s", startup_errors)
    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=FLASK_ENV == "development")
