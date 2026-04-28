<<<<<<< HEAD
# frauddetection
=======
# Real-Time Financial Anomaly Detection System

This project is a production-ready baseline for fraud/anomaly detection in fintech settings where labeled fraud data is unavailable.

It includes:

- Synthetic transaction data generation
- Unsupervised anomaly modeling (`IsolationForest`, optional `DBSCAN` benchmark)
- Robust preprocessing (`RobustScaler`)
- Real-time Flask API inference
- Risk scoring and explainability
- Persistent SQLite transaction storage
- Neon dark-mode security dashboard frontend
- Deployment configs for Render/Railway (backend) and Netlify/Vercel (frontend)
- Docker + docker-compose for local/prod parity

## 1) Project Structure

```text
frauddetector/
  app.py
  requirements.txt
  Procfile
  runtime.txt
  render.yaml
  netlify.toml
  vercel.json
  Dockerfile
  docker-compose.yml
  .dockerignore
  README.md
  models/
    isolation_forest.joblib
    robust_scaler.joblib
    model_metadata.json
  scripts/
    train_model.py
  src/
    __init__.py
    config.py
    api/
      __init__.py
      routes.py
    services/
      __init__.py
      model_service.py
      risk_service.py
      transaction_log.py
    utils/
      __init__.py
      validators.py
  frontend/
    config.js
    Dockerfile
    index.html
    styles.css
    app.js
```

## 2) Why `RobustScaler` over `StandardScaler`

Financial transaction features are often heavy-tailed and outlier-rich.

- `StandardScaler` uses mean/std, which are sensitive to outliers.
- `RobustScaler` uses median and IQR, which are more stable under extreme values.

This makes anomaly boundaries more reliable and reduces distortion caused by rare but very large transactions.

## 3) Anomaly Detection Intuition

### Isolation Forest

Isolation Forest builds many random trees. Anomalies are easier to isolate, so they tend to have shorter path lengths.

Mathematically, anomaly score is tied to expected path length:

- Shorter average path length => more anomalous
- Longer average path length => more normal

Scikit-learn convention:

- `predict = 1` -> inlier (normal)
- `predict = -1` -> outlier (anomaly)

`-1` is a library-defined label for outliers, not a probability.

### DBSCAN (limitations for real-time)

DBSCAN clusters by density. Noise points are labeled `-1`.

Limitations for strict real-time APIs:

- No native, stable out-of-sample `predict` for new points in sklearn DBSCAN
- Inference usually requires nearest-neighbor heuristics or full refit
- Less operationally clean than Isolation Forest for streaming APIs

## 4) Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## 5) Train the Model

```bash
python scripts/train_model.py
```

This generates:

- `models/isolation_forest.joblib`
- `models/robust_scaler.joblib`
- `models/model_metadata.json`
- Optional chart: `models/anomaly_scatter.png`

## 6) Run Backend Locally

```bash
python app.py
```

API base: `http://127.0.0.1:5000`

### Endpoints

- `GET /api/health`
- `GET /api/metrics`
- `GET /api/transactions/recent?limit=20`
- `POST /api/verify_transaction`

### Sample Request

```json
{
  "amount": 735.2,
  "distance": 5.3,
  "time_delta": 42.0
}
```

### Sample Response

```json
{
  "is_fraudulent": false,
  "risk_level": "LOW",
  "risk_score": 0.17,
  "prediction_label": 1,
  "explanation": {
    "top_risk_factors": [
      "Time_Since_Last_Transaction above typical range"
    ]
  }
}
```

## 7) Frontend

Open `frontend/index.html` directly or serve it using any static host.

By default, frontend reads API base from:

- URL query `?apiBase=...` (highest priority)
- `frontend/config.js` using `window.__API_BASE__`
- `localStorage.apiBase`
- fallback `http://127.0.0.1:5000`

## 8) Deployment

### Backend (Render/Railway)

Required files are included:

- `Procfile`: `web: gunicorn app:app`
- `requirements.txt`
- `runtime.txt`
- `render.yaml` (Render blueprint)

Environment variables:

- `FLASK_ENV=production`
- `PORT` (platform sets automatically)
- `MODEL_PATH=models/isolation_forest.joblib`
- `SCALER_PATH=models/robust_scaler.joblib`
- `TRANSACTION_DB_PATH=/var/data/transactions.db` (persistent disk path)

### Frontend (Netlify/Vercel)

One-click configs included:

- Netlify: [netlify.toml](./netlify.toml)
- Vercel: [vercel.json](./vercel.json)

Deploy static frontend from `frontend/`.

Set API base on deployed UI:

1. Open site with query param: `?apiBase=https://your-api.onrender.com`
2. Or set in `frontend/config.js`:
   `window.__API_BASE__ = "https://your-api.onrender.com";`
3. Or in browser console:
   `localStorage.setItem("apiBase","https://your-api.onrender.com")`

## 9) Docker (Full Parity)

### Backend image only

```bash
docker build -t frauddetector-api .
docker run --rm -p 5000:5000 \
  -e FLASK_ENV=production \
  -e MODEL_PATH=/app/models/isolation_forest.joblib \
  -e SCALER_PATH=/app/models/robust_scaler.joblib \
  -e TRANSACTION_DB_PATH=/app/data/transactions.db \
  -v %cd%/models:/app/models \
  -v %cd%/data:/app/data \
  frauddetector-api
```

### Full stack with docker-compose

```bash
docker compose up --build
```

Services:

- API: `http://localhost:5000`
- Frontend: `http://localhost:8080`

SQLite persistence:

- DB file: `./data/transactions.db`
- Mounted into API container for durable local storage

## 10) Testing Guide

### Postman

1. `POST /api/verify_transaction`
2. Content-Type: `application/json`
3. Test cases:
   - Normal: low amount, short distance, moderate time delta
   - Suspicious: very high amount, large distance, very low time delta
   - Invalid payload: missing keys or wrong types

### Browser

1. Open dashboard
2. Submit normal and suspicious transactions
3. Confirm:
   - Green "APPROVED" for low risk
   - Red blinking alert for critical risk
   - Loading "SCANNING..." animation
   - API-down error handling
>>>>>>> 8ffef6b (Initial commit)
