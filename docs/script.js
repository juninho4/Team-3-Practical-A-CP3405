"use strict";

const DATA_URL = "./data/latest_prediction.json";
const providerOrder = ["groq", "gemini", "openrouter"];
const symbols = ["SPX", "NDX", "IWM"];

function text(id, value) {
  const element = document.getElementById(id);
  if (element) element.textContent = value ?? "Unavailable";
}

function safeValue(value, fallback = "Unavailable") {
  return typeof value === "string" && value.trim() ? value.trim() : fallback;
}

function statusLabel(status) {
  const normalized = safeValue(status, "unavailable").toLowerCase();
  return normalized.charAt(0).toUpperCase() + normalized.slice(1);
}

function buildPredictionCards(predictions = {}) {
  const grid = document.getElementById("prediction-grid");
  grid.replaceChildren();

  symbols.forEach((symbol) => {
    const prediction = predictions[symbol] || {};
    const card = document.createElement("article");
    card.className = "prediction-card";

    const topline = document.createElement("div");
    topline.className = "prediction-symbol";

    const heading = document.createElement("h3");
    heading.textContent = symbol;

    const direction = document.createElement("span");
    direction.className = "direction-pill";
    direction.textContent = safeValue(prediction.direction);

    const range = document.createElement("strong");
    range.className = "prediction-range";
    range.textContent = safeValue(prediction.range);

    const caption = document.createElement("p");
    caption.textContent = "Suggested weekly percentage range";

    topline.append(heading, direction);
    card.append(topline, range, caption);
    grid.append(card);
  });
}

function buildProviderCards(models = {}) {
  const grid = document.getElementById("provider-grid");
  grid.replaceChildren();

  providerOrder.forEach((key) => {
    const provider = models[key] || {};
    const status = safeValue(provider.status, "unavailable").toLowerCase();
    const card = document.createElement("article");
    card.className = `provider-card ${status}`;

    const topline = document.createElement("div");
    topline.className = "provider-topline";

    const identity = document.createElement("div");
    const heading = document.createElement("h3");
    heading.textContent = safeValue(provider.name, key);
    const model = document.createElement("div");
    model.className = "provider-model";
    model.textContent = safeValue(provider.model, "Model not reported");
    identity.append(heading, model);

    const pill = document.createElement("span");
    pill.className = `status-pill ${status}`;
    pill.textContent = statusLabel(status);
    topline.append(identity, pill);

    const error = document.createElement("div");
    error.className = "error-code";
    error.textContent = safeValue(provider.error_code, status === "success" ? "No error" : "No code reported");

    const detail = document.createElement("p");
    detail.textContent = safeValue(
      provider.detail,
      status === "success" ? "Response saved successfully." : "See the weekly API call log for details."
    );

    card.append(topline, error, detail);
    grid.append(card);
  });
}

function fillEvidence(summaries = {}) {
  text("r3-summary", safeValue(summaries.r3, "No R3 summary available."));
  text("r4-summary", safeValue(summaries.r4, "No R4 summary available."));
  text("r5-summary", safeValue(summaries.r5, "No R5 summary available."));
  text("r8-summary", safeValue(summaries.r8, "No R8 summary available."));
}

function fillSources(evidence = {}, sourceUrl = "") {
  const fileNames = [
    evidence.r3_file,
    evidence.r4_file,
    evidence.llm_comparison,
    evidence.api_call_log,
  ].filter(Boolean);

  const r5Count = Array.isArray(evidence.r5_files) ? evidence.r5_files.length : 0;
  const suffix = r5Count ? ` R5 includes ${r5Count} CSV file(s).` : "";
  text(
    "source-files",
    fileNames.length
      ? `${fileNames.join(" · ")}.${suffix}`
      : `No source path was exported.${suffix}`
  );

  const link = document.getElementById("source-link");
  if (sourceUrl) {
    link.href = sourceUrl;
    link.hidden = false;
  }
}

function render(data) {
  text("week", safeValue(data.week, "Unknown"));
  text("generated-at", safeValue(data.generated_at, "Generation time unavailable"));
  text("regime", safeValue(data.regime, "Uncertain"));
  text("confidence", safeValue(data.confidence, "Unknown"));
  text("pipeline-status", safeValue(data.pipeline_status));

  const successful = Object.values(data.models || {}).filter(
    (provider) => provider?.status === "success"
  ).length;
  text("provider-count", `${successful}/3 AI providers succeeded`);

  buildPredictionCards(data.predictions);
  buildProviderCards(data.models);
  fillEvidence(data.summaries);
  fillSources(data.evidence, data.source_url);
}

async function loadDashboard() {
  try {
    const response = await fetch(DATA_URL, { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    render(data);
  } catch (error) {
    console.error("Dashboard load failed:", error);
    document.getElementById("load-error").hidden = false;
    text("pipeline-status", "Data unavailable");
    buildPredictionCards({});
    buildProviderCards({});
  }
}

loadDashboard();
