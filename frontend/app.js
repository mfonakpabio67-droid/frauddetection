function safeGetStorage(key) {
  try {
    return window.localStorage.getItem(key);
  } catch (_) {
    return null;
  }
}

function safeSetStorage(key, value) {
  try {
    window.localStorage.setItem(key, value);
  } catch (_) {
    // Ignore storage write failures in sandboxed previews.
  }
}

const queryParams = new URLSearchParams(window.location.search);
const queryApiBase = queryParams.get("apiBase");
const queryMockMode = queryParams.get("mock");
const storedApiBase = safeGetStorage("apiBase");
const configuredApiBase = window.__API_BASE__ || "";
const API_BASE = queryApiBase || configuredApiBase || storedApiBase || "http://127.0.0.1:5000";
const USE_MOCK_MODE =
  queryMockMode === "1" ||
  queryMockMode === "true" ||
  (queryMockMode === null && Boolean(window.__USE_MOCK_MODE__));

if (queryApiBase) {
  safeSetStorage("apiBase", queryApiBase);
}

const form = document.getElementById("txnForm");
const statusBox = document.getElementById("status");
const resultBox = document.getElementById("result");
const resultIcon = document.getElementById("resultIcon");
const resultTitle = document.getElementById("resultTitle");
const resultMeta = document.getElementById("resultMeta");
const resultReason = document.getElementById("resultReason");
const scanButton = document.getElementById("scanButton");
const recentLogs = document.getElementById("recentLogs");

const metricApi = document.getElementById("metricApi");
const metricTotal = document.getElementById("metricTotal");
const metricFraud = document.getElementById("metricFraud");
const metricRatio = document.getElementById("metricRatio");
const metricAccuracy = document.getElementById("metricAccuracy");

const txnId = document.getElementById("txnId");
const txnTime = document.getElementById("txnTime");
const txnScore = document.getElementById("txnScore");
const txnPrediction = document.getElementById("txnPrediction");

metricApi.textContent = API_BASE.replace(/^https?:\/\//, "");
if (USE_MOCK_MODE) {
  metricApi.textContent = `${metricApi.textContent} (mock fallback)`;
}

let mockStore = {
  total: 1248,
  fraud: 142,
  recent: [
    { is_fraudulent: true, amount: 5200, distance: 150, time_delta: 1, risk_level: "CRITICAL" },
    { is_fraudulent: true, amount: 3800, distance: 98, time_delta: 3, risk_level: "HIGH" },
    { is_fraudulent: false, amount: 120, distance: 2, time_delta: 45, risk_level: "LOW" },
    { is_fraudulent: false, amount: 75.5, distance: 1, time_delta: 60, risk_level: "LOW" },
    { is_fraudulent: true, amount: 9999, distance: 200, time_delta: 2, risk_level: "CRITICAL" },
  ],
};

function setLoading(isLoading) {
  statusBox.classList.toggle("hidden", !isLoading);
  scanButton.disabled = isLoading;
  scanButton.innerHTML = isLoading
    ? '<i data-lucide="loader-circle"></i> SCANNING...'
    : '<i data-lucide="radar"></i> SCAN TRANSACTION';
  if (window.lucide && typeof window.lucide.createIcons === "function") {
    window.lucide.createIcons();
  }
}

function randomTxnId() {
  const n = Math.floor(Math.random() * 9000) + 1000;
  const d = new Date();
  const stamp = `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, "0")}${String(d.getDate()).padStart(2, "0")}`;
  return `TXN_${stamp}_${n}`;
}

function applyResultState(data) {
  resultBox.classList.remove("safe", "fraud", "error");
  const reasonList = data.explanation?.top_risk_factors || [];
  resultReason.textContent = `Reason: ${reasonList.join("; ")}`;
  resultMeta.textContent = `Risk Level: ${data.risk_level} | Risk Score: ${Number(data.risk_score).toFixed(4)}`;
  txnScore.textContent = `${Number(data.risk_score).toFixed(4)} / 1.0000`;
  txnTime.textContent = new Date().toLocaleString();
  txnId.textContent = randomTxnId();

  if (data.is_fraudulent) {
    resultBox.classList.add("fraud");
    resultIcon.textContent = "!";
    resultTitle.textContent = "FRAUD DETECTED";
    txnPrediction.textContent = "Anomalous Transaction";
    return;
  }

  resultBox.classList.add("safe");
  resultIcon.textContent = "OK";
  resultTitle.textContent = "TRANSACTION APPROVED";
  txnPrediction.textContent = "Normal Transaction";
}

function applyErrorState(message) {
  resultBox.classList.remove("safe", "fraud");
  resultBox.classList.add("error");
  resultIcon.textContent = "X";
  resultTitle.textContent = "API UNREACHABLE";
  resultMeta.textContent = "Unable to verify transaction at this time.";
  resultReason.textContent = `Reason: ${message}`;
  txnPrediction.textContent = "Inference Failed";
}

function renderLogs(items) {
  if (!Array.isArray(items) || items.length === 0) {
    recentLogs.innerHTML = '<div class="log-row"><span>No data</span><span>-</span><span>-</span><span>-</span><span>-</span></div>';
    return;
  }

  recentLogs.innerHTML = items
    .slice(0, 8)
    .map((item) => {
      const statusClass = item.is_fraudulent ? "fraud" : "normal";
      const statusText = item.is_fraudulent ? "FRAUD" : "NORMAL";
      const amount = Number(item.amount || 0).toLocaleString(undefined, { style: "currency", currency: "USD" });
      const distance = `${Number(item.distance || 0).toFixed(1)} km`;
      const t = `${Number(item.time_delta || 0).toFixed(1)} min`;
      const level = String(item.risk_level || "LOW");
      return `
        <div class="log-row">
          <span class="status-pill ${statusClass}">${statusText}</span>
          <span>${amount}</span>
          <span>${distance}</span>
          <span>${t}</span>
          <span>${level}</span>
        </div>
      `;
    })
    .join("");
}

function mockPredict(payload) {
  const amountRisk = Math.min(payload.amount / 10000, 1);
  const distRisk = Math.min(payload.distance / 200, 1);
  const velocityRisk = payload.time_delta <= 3 ? 1 : Math.min(20 / payload.time_delta, 1);
  const riskScore = Math.min(0.55 * amountRisk + 0.3 * distRisk + 0.25 * velocityRisk, 1);
  const isFraud = riskScore >= 0.65;

  let riskLevel = "LOW";
  if (riskScore >= 0.9) riskLevel = "CRITICAL";
  else if (riskScore >= 0.7) riskLevel = "HIGH";
  else if (riskScore >= 0.4) riskLevel = "MEDIUM";

  const reasons = [];
  if (payload.amount > 3000) reasons.push("Transaction_Amount above typical range");
  if (payload.distance > 60) reasons.push("Distance_From_Home above typical range");
  if (payload.time_delta < 4) reasons.push("Time_Since_Last_Transaction below typical range");
  if (reasons.length === 0) reasons.push("No extreme feature deviation detected");

  return {
    is_fraudulent: isFraud,
    risk_level: riskLevel,
    risk_score: Number(riskScore.toFixed(4)),
    explanation: { top_risk_factors: reasons.slice(0, 2) },
  };
}

async function fetchMetrics() {
  if (USE_MOCK_MODE) {
    const ratio = mockStore.total > 0 ? mockStore.fraud / mockStore.total : 0;
    const confidence = Math.max(80, 100 - ratio * 100 * 0.4);
    metricTotal.textContent = mockStore.total.toLocaleString();
    metricFraud.textContent = mockStore.fraud.toLocaleString();
    metricRatio.textContent = `${(ratio * 100).toFixed(2)}%`;
    metricAccuracy.textContent = `${confidence.toFixed(1)}%`;
    return;
  }
  try {
    const response = await fetch(`${API_BASE}/api/metrics`);
    if (!response.ok) {
      return;
    }
    const metrics = await response.json();
    const total = Number(metrics.total_transactions_logged || 0);
    const fraud = Number(metrics.fraud_transactions_logged || 0);
    const ratio = Number(metrics.fraud_ratio || 0);
    const confidence = Math.max(80, 100 - ratio * 100 * 0.4);

    metricTotal.textContent = total.toLocaleString();
    metricFraud.textContent = fraud.toLocaleString();
    metricRatio.textContent = `${(ratio * 100).toFixed(2)}%`;
    metricAccuracy.textContent = `${confidence.toFixed(1)}%`;
  } catch (_) {
    // Keep existing values if metrics endpoint is unavailable.
  }
}

async function fetchRecentLogs() {
  if (USE_MOCK_MODE) {
    renderLogs(mockStore.recent);
    return;
  }
  try {
    const response = await fetch(`${API_BASE}/api/transactions/recent?limit=8`);
    if (!response.ok) {
      renderLogs([]);
      return;
    }
    const payload = await response.json();
    renderLogs(payload.transactions || []);
  } catch (_) {
    renderLogs([]);
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  setLoading(true);

  const payload = {
    amount: Number(document.getElementById("amount").value),
    distance: Number(document.getElementById("distance").value),
    time_delta: Number(document.getElementById("timeDelta").value),
  };

  try {
    let data;
    if (USE_MOCK_MODE) {
      await new Promise((resolve) => setTimeout(resolve, 850));
      data = mockPredict(payload);
      mockStore.total += 1;
      if (data.is_fraudulent) mockStore.fraud += 1;
      mockStore.recent.unshift({
        is_fraudulent: data.is_fraudulent,
        amount: payload.amount,
        distance: payload.distance,
        time_delta: payload.time_delta,
        risk_level: data.risk_level,
      });
      mockStore.recent = mockStore.recent.slice(0, 8);
    } else {
      const response = await fetch(`${API_BASE}/api/verify_transaction`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || "Unknown API error");
      }
    }

    applyResultState(data);
    await Promise.all([fetchMetrics(), fetchRecentLogs()]);
  } catch (error) {
    applyErrorState(error.message);
  } finally {
    setLoading(false);
  }
});

if (window.lucide && typeof window.lucide.createIcons === "function") {
  window.lucide.createIcons();
}

fetchMetrics();
fetchRecentLogs();
setInterval(fetchMetrics, 10000);
setInterval(fetchRecentLogs, 12000);
