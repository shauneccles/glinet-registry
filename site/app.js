"use strict";

const els = {
  device: document.getElementById("device"),
  search: document.getElementById("search"),
  availableOnly: document.getElementById("available-only"),
  notWrapped: document.getElementById("not-wrapped"),
  discoveredOnly: document.getElementById("discovered-only"),
  openrpc: document.getElementById("openrpc"),
  count: document.getElementById("count"),
  capabilities: document.getElementById("capabilities"),
  results: document.getElementById("results"),
};

function renderCapabilities(caps) {
  if (!caps || !(caps.country_code || caps.software_feature || caps.hardware_feature)) {
    els.capabilities.hidden = true;
    els.capabilities.innerHTML = "";
    return;
  }
  const sw = caps.software_feature || {};
  const swOn = Object.keys(sw).filter((k) => sw[k] === true).sort();
  const region = caps.country_code ? `region <b>${escapeHtml(caps.country_code)}</b>` : "";
  const features = swOn.length ? `features: ${swOn.map(escapeHtml).join(", ")}` : "";
  const detail = JSON.stringify(
    { software_feature: sw, hardware_feature: caps.hardware_feature || {} }, null, 2);
  els.capabilities.innerHTML =
    `<span class="cap-summary">${[region, features].filter(Boolean).join(" · ")}</span>` +
    `<details><summary>raw capabilities</summary><pre>${escapeHtml(detail)}</pre></details>`;
  els.capabilities.hidden = false;
}

const PRESENT = new Set(["available", "needs_params"]);
let current = null;

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function badge(text, cls) {
  return `<span class="badge ${escapeHtml(cls)}">${escapeHtml(text)}</span>`;
}

function methodRow(service, method, rec) {
  const present = PRESENT.has(rec.status);
  let cov = "";
  if (rec.covered_by) cov = badge(`gli4py: ${rec.covered_by}`, "cov-yes");
  else if (present) cov = badge("not yet in gli4py", "cov-no");
  let detail = "";
  if (rec.params || rec.schema) {
    const body = JSON.stringify({ params: rec.params, schema: rec.schema }, null, 2);
    detail = `<pre class="detail">${escapeHtml(body)}</pre>`;
  }
  return `<div class="method">
    <div class="mhead">
      <code>${escapeHtml(method)}</code>
      ${badge(rec.status, "st-" + rec.status)}
      ${badge(rec.risk, "rk-" + rec.risk)}
      ${cov}
    </div>${detail}</div>`;
}

function render() {
  if (!current) return;
  const q = els.search.value.trim().toLowerCase();
  const availOnly = els.availableOnly.checked;
  const nw = els.notWrapped.checked;
  const disc = els.discoveredOnly.checked;
  let shown = 0;
  const parts = [];
  for (const service of Object.keys(current.services).sort()) {
    const methods = current.services[service];
    const rows = [];
    for (const method of Object.keys(methods).sort()) {
      const rec = methods[method];
      const present = PRESENT.has(rec.status);
      if (availOnly && !present) continue;
      if (nw && !(present && rec.covered_by == null)) continue;
      if (disc && rec.status !== "discovered") continue;
      if (q && !`${service}.${method}`.toLowerCase().includes(q)) continue;
      rows.push(methodRow(service, method, rec));
      shown += 1;
    }
    if (rows.length) parts.push(`<section class="service"><h2>${escapeHtml(service)}</h2>${rows.join("")}</section>`);
  }
  els.results.innerHTML = parts.join("") || "<p class='empty'>No methods match.</p>";
  els.count.textContent = `${shown} method${shown === 1 ? "" : "s"}`;
}

async function loadDevice(id) {
  try {
    const res = await fetch(`data/devices/${id}.json`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    current = await res.json();
    els.openrpc.href = `data/openrpc/${id}.openrpc.json`;
    els.openrpc.download = `${id}.openrpc.json`;
    els.openrpc.hidden = false;
    renderCapabilities(current.capabilities);
    render();
  } catch (err) {
    els.results.innerHTML = "<p class='empty'>Could not load this device's data.</p>";
  }
}

async function loadManifest() {
  let manifest;
  try {
    manifest = await (await fetch("data/index.json")).json();
  } catch (err) {
    els.results.innerHTML = "<p class='empty'>Could not load data/index.json.</p>";
    return;
  }
  if (!manifest.devices || !manifest.devices.length) {
    els.results.innerHTML = "<p class='empty'>No device data yet. Capture one with <code>glinet-profiler</code>.</p>";
    return;
  }
  for (const d of manifest.devices) {
    const opt = document.createElement("option");
    opt.value = d.id;
    const writes = d.discovered_count ? `, ${d.discovered_count} discovered` : "";
    opt.textContent = `${d.model} (${d.firmware_version}) — ${d.available_count} available${writes}`;
    els.device.appendChild(opt);
  }
  await loadDevice(manifest.devices[0].id);
}

els.device.addEventListener("change", (e) => loadDevice(e.target.value));
for (const el of [els.search, els.availableOnly, els.notWrapped, els.discoveredOnly]) {
  el.addEventListener("input", render);
}
els.results.addEventListener("click", (e) => {
  const m = e.target.closest(".method");
  if (m) m.classList.toggle("open");
});

loadManifest();
