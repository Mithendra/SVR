// Daily Sales Entry screen. Ported from
// docs/01-BRD-Requirement-Gathering/daily_sales_report_branded.html, with the demo
// functions replaced by loopback-API calls. The backend's /calc result is
// authoritative; calc-mirror only fills the gap between keystroke and response.

import { api, getToken } from "../../lib/api.js";
import * as mirror from "../../lib/calc-mirror.js";

const OIL_KEYS = ["oil1", "oil2", "oil3", "oil4", "oil5"];

const $ = (id) => document.getElementById(id);
const val = (id) => ($(id) ? $(id).value : "");
const setVal = (id, v) => {
  const el = $(id);
  if (el) el.value = v === null || v === undefined ? "" : v;
};

let entryId = null; // set after first Save -> subsequent saves PUT
let calcTimer = null;
let oilLabels = { ...Object.fromEntries(OIL_KEYS.map((k) => [k, k])) };

// --------------------------------------------------------------------- build DOM

function blankRow(cells) {
  const tr = document.createElement("tr");
  tr.innerHTML = cells;
  return tr;
}

function buildOilRows() {
  const body = $("oil-rows");
  const ds = $("ds-oil-rows");
  body.innerHTML = "";
  ds.innerHTML = "";
  OIL_KEYS.forEach((k) => {
    body.appendChild(
      blankRow(
        `<td data-oil-label="${k}">${oilLabels[k]}</td>` +
          `<td><input id="${k}-qty" data-calc></td>` +
          `<td><input id="${k}-rate" disabled placeholder="auto (Rate Master)"></td>` +
          `<td><input id="${k}-opening" disabled placeholder="auto (Inventory)"></td>` +
          `<td><input id="${k}-closing" disabled placeholder="auto"></td>` +
          `<td><input id="${k}-amount" disabled placeholder="auto"></td>`
      )
    );
    ds.appendChild(blankRow(`<td>${oilLabels[k]}</td><td><input id="ds-${k}" disabled></td>`));
  });
}

function addCcRow() {
  $("cc-rows").appendChild(
    blankRow(
      "<td><input></td><td><input></td><td><input></td><td><input></td>" +
        '<td><input class="cc-amount" data-calc></td>'
    )
  );
}
function addNcRow() {
  $("nc-rows").appendChild(
    blankRow(
      "<td><input></td><td><input></td>" +
        '<td><input class="nc-ltrs" data-calc></td>' +
        '<td><input class="nc-rate" data-calc></td>' +
        '<td><input class="nc-amount" disabled placeholder="auto"></td>' +
        "<td><input></td>"
    )
  );
}
function addOcRow() {
  $("oc-rows").appendChild(
    blankRow('<td><input></td><td><input class="oc-amount" data-calc></td><td><input></td><td><input></td>')
  );
}

// ------------------------------------------------------------------- form <-> API

function readForm() {
  const oils = OIL_KEYS.map((k) => ({
    label: oilLabels[k],
    qty: val(`${k}-qty`),
    rate: val(`${k}-rate`),
    opening: val(`${k}-opening`),
  }));
  return {
    pump_serial: val("pump-serial"),
    shift_date: val("shift-date"),
    hs: { current: val("hs-current"), last: val("hs-last"), rate: val("hs-rate") },
    ms: { current: val("ms-current"), last: val("ms-last"), rate: val("ms-rate") },
    oils,
    expenses: [...document.querySelectorAll(".exp")].map((i) => i.value),
    credit_card_amounts: [...document.querySelectorAll(".cc-amount")].map((i) => i.value),
    new_credits: [...document.querySelectorAll("#nc-rows tr")].map((tr) => ({
      ltrs: tr.querySelector(".nc-ltrs").value,
      rate: tr.querySelector(".nc-rate").value,
    })),
    old_credit_amounts: [...document.querySelectorAll(".oc-amount")].map((i) => i.value),
    phone_pay_settled: val("pp-settled"),
    phone_pay_unsettled: val("pp-unsettled"),
    night_cash: val("night-cash"),
  };
}

function applyResult(r) {
  setVal("hs-cons", r.hs.cons);
  setVal("hs-amount", r.hs.amount);
  setVal("ms-cons", r.ms.cons);
  setVal("ms-amount", r.ms.amount);
  setVal("gas-total", r.gas_total);

  r.oils.forEach((o, i) => {
    const k = OIL_KEYS[i];
    if (!k) return;
    setVal(`${k}-closing`, o.closing);
    setVal(`${k}-amount`, o.amount);
  });
  setVal("oil-total", r.oil_total);

  setVal("exp-total", r.expenses_total);
  setVal("cc-total", r.credit_cards_total);
  document.querySelectorAll(".nc-amount").forEach((el, i) => {
    el.value = r.new_credit_amounts[i] ?? "";
  });
  setVal("nc-total", r.new_credits_total);

  setVal("sum-cash", r.sum_cash);
  setVal("sum-expenses", r.sum_expenses);
  setVal("sum-newcredits", r.sum_new_credits);
  setVal("sum-cc", r.sum_credit_cards);
  setVal("sum-netbal", r.net_bal_hand_off);
  setVal("sum-oldcredit", r.sum_old_credit);

  setVal("ds-hs", r.daily_summary.hs);
  setVal("ds-ms", r.daily_summary.ms);
  (r.daily_summary.oils || []).forEach((q, i) => setVal(`ds-${OIL_KEYS[i]}`, q));
}

function refresh() {
  const payload = readForm();
  applyResult(mirror.compute(payload)); // instant
  clearTimeout(calcTimer);
  calcTimer = setTimeout(async () => {
    try {
      applyResult(await api.post("/daily-sales-entry/calc", payload)); // authoritative
    } catch {
      /* keep the mirror result on transient failure */
    }
  }, 250);
}

async function loadPrefill() {
  const params = new URLSearchParams({
    pump_serial: val("pump-serial"),
    shift_date: val("shift-date"),
  });
  const p = await api.get(`/daily-sales-entry/prefill?${params.toString()}`);
  oilLabels = p.oil_labels || oilLabels;
  buildOilRows();

  setVal("hs-last", p.hs_last);
  setVal("ms-last", p.ms_last);
  setVal("hs-rate", p.sell_rate_hs);
  setVal("ms-rate", p.sell_rate_ms);
  OIL_KEYS.forEach((k) => setVal(`${k}-rate`, p.oil_rates ? p.oil_rates[k] : ""));

  $("carried-note").textContent = p.carried_from
    ? `Last Shift Reading carried from ${p.carried_from} (auto @ 23:59 IST).`
    : "No prior reading for this pump — Last Shift Reading starts blank.";
  refresh();
}

async function save() {
  const status = $("save-status");
  const payload = readForm();
  status.className = "status-line";
  status.textContent = "Saving…";
  try {
    const saved = entryId
      ? await api.put(`/daily-sales-entry/${entryId}`, payload)
      : await api.post("/daily-sales-entry", payload);
    entryId = saved.id;
    applyResult(saved.result);
    $("last-updated-by").textContent = saved.last_updated_by;
    $("last-updated-time").textContent = new Date(saved.last_updated_at).toLocaleString();
    status.className = "status-line ok";
    status.textContent = `Saved (entry #${saved.id}). Net Bal Hand off ${saved.net_bal_hand_off}.`;
  } catch (err) {
    status.className = "status-line err";
    status.textContent = `Save failed — ${err.message || err}`;
  }
}

async function stubAction(label, fn) {
  const status = $("save-status");
  try {
    await fn();
  } catch (err) {
    status.className = "status-line";
    status.textContent =
      err.status === 501 ? `${label} is not yet available.` : `${label} failed — ${err.message || err}`;
  }
}

// --------------------------------------------------------------------------- init

function wireToggles() {
  document.querySelectorAll(".theme-toggle button").forEach((btn) => {
    btn.addEventListener("click", () => {
      const map = { red: "#e31e24", blue: "#0033a0", orange: "#f37022" };
      document.documentElement.style.setProperty("--io-accent", map[btn.dataset.accent]);
      document.querySelectorAll(".theme-toggle button").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
    });
  });
  document.querySelectorAll(".lang-toggle button").forEach((btn) => {
    btn.addEventListener("click", () => {
      const lang = btn.dataset.lang;
      document.querySelectorAll(".tt").forEach((el) => {
        el.textContent = el.dataset[lang] || el.textContent;
      });
      document.querySelectorAll(".lang-toggle button").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
    });
  });
}

async function init() {
  if (!getToken()) {
    window.location.href = "../../index.html";
    return;
  }
  $("shift-date").value = new Date().toISOString().slice(0, 10);
  buildOilRows();
  addCcRow();
  addCcRow();
  addNcRow();
  addNcRow();
  addOcRow();
  addOcRow();

  try {
    const me = await api.me();
    setVal("ds-name", me.full_name);
    setVal("mgr-name", me.full_name);
    setVal("verify-name", me.full_name);
  } catch {
    window.location.href = "../../index.html";
    return;
  }

  wireToggles();

  document.body.addEventListener("input", (e) => {
    if (e.target.matches("[data-calc]")) refresh();
  });
  $("pump-serial").addEventListener("change", () => {
    entryId = null;
    loadPrefill();
  });
  $("shift-date").addEventListener("change", () => {
    entryId = null;
    loadPrefill();
  });
  document.querySelectorAll("[data-add]").forEach((btn) => {
    btn.addEventListener("click", () => {
      ({ cc: addCcRow, nc: addNcRow, oc: addOcRow })[btn.dataset.add]();
      refresh();
    });
  });

  $("save-btn").addEventListener("click", save);
  $("print-btn").addEventListener("click", () => window.print());
  document.querySelectorAll("[data-blank]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      $("pump-serial").value = btn.dataset.blank;
      setVal("hs-current", "");
      setVal("ms-current", "");
      await loadPrefill();
      window.print();
    });
  });
  $("scan-btn").addEventListener("click", () =>
    stubAction("Scan / Upload (OCR)", () => api.post("/daily-sales-entry/ocr"))
  );
  $("import-btn").addEventListener("click", () =>
    stubAction("Import from Excel", () => api.post("/daily-sales-entry/import-excel"))
  );
  $("export-btn").addEventListener("click", () =>
    stubAction("Export to Excel", () => api.get("/daily-sales-entry/0/export-excel"))
  );

  await loadPrefill();
}

init();
