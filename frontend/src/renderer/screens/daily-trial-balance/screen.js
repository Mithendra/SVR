// Daily Trial Balance screen (SDD 5.8 / 9). Manager + Owner. Sections 1/6/7 are
// computed by the backend engine; Section 3 consumption is pulled from Daily Sales
// Summary; the remaining sections are a manual JSON block pending SDD ADR-1.

import { api, getToken } from "../../lib/api.js";

const $ = (id) => document.getElementById(id);
const txt = (id, v) => {
  $(id).textContent = v === null || v === undefined ? "—" : v;
};

function render(view) {
  $("status-tag").textContent = view.status;
  const i = view.inputs;
  $("hs-y").value = i.s1_hs_yesterday ?? "";
  $("hs-c").value = i.s1_hs_current ?? "";
  $("ms-y").value = i.s1_ms_yesterday ?? "";
  $("ms-c").value = i.s1_ms_current ?? "";
  $("cash-bv").value = i.s54_cash_book_value ?? "";
  $("manual-json").value = JSON.stringify(view.manual, null, 2);

  for (const f of ["hs", "ms"]) {
    const s = view.computed.section1[f];
    txt(`${f}-diff`, s.diff);
    txt(`${f}-cons`, s.consumption);
    txt(`${f}-cpd`, s.computer_pump_diff);
    txt(`${f}-bl`, s.benefit_loss);
    txt(`${f}-dt`, s.deduct_testing);
    txt(`${f}-sl`, s.stock_ltrs);
    txt(`${f}-sa`, s.stock_amount);
  }
  txt("hs-br", view.pulled.buy_rate_hs);
  txt("ms-br", view.pulled.buy_rate_ms);
  txt("s6-total", view.computed.section6.total);
  txt("s7-2", view.computed.section7["7_2_stock_value"]);
  txt("s7-3", view.computed.section7["7_3_total"]);

  $("s3-src").textContent =
    view.pulled.s3_source === "daily_sales_summary"
      ? `Section 3 consumption pulled from Daily Sales Summary (HS ${view.pulled.s3_hs_consumption ?? "—"} / MS ${view.pulled.s3_ms_consumption ?? "—"} L).`
      : "No Daily Sales Summary for this date yet — Section 3 consumption is unavailable, so the derived columns stay blank.";

  const locked = view.status === "finalized";
  for (const id of ["hs-y", "hs-c", "ms-y", "ms-c", "cash-bv", "manual-json"]) {
    $(id).disabled = locked;
  }
  $("save-btn").disabled = locked;
  $("finalize-btn").disabled = locked;
  $("body").style.display = "block";
}

function payload() {
  const num = (id) => {
    const n = parseFloat($(id).value);
    return isNaN(n) ? null : n;
  };
  let manual = {};
  try {
    manual = $("manual-json").value.trim() ? JSON.parse($("manual-json").value) : {};
  } catch {
    throw new Error("Manual JSON is not valid JSON.");
  }
  return {
    s1_hs_yesterday: num("hs-y"),
    s1_hs_current: num("hs-c"),
    s1_ms_yesterday: num("ms-y"),
    s1_ms_current: num("ms-c"),
    s54_cash_book_value: num("cash-bv"),
    manual,
  };
}

async function load() {
  const st = $("tb-status");
  const wanted = $("tb-date").value;
  try {
    const view = await api.get(`/daily-trial-balance/${wanted}`);
    // Ignore a slow response if the user has since changed the date.
    if ($("tb-date").value !== wanted) return;
    render(view);
    st.textContent = "";
  } catch (err) {
    st.className = "status-line err";
    st.textContent = err.message || String(err);
  }
}

async function save() {
  const st = $("save-status");
  try {
    render(await api.put(`/daily-trial-balance/${$("tb-date").value}`, payload()));
    st.className = "status-line ok";
    st.textContent = "Saved; formulas recalculated.";
  } catch (err) {
    st.className = "status-line err";
    st.textContent = `Save failed — ${err.message || err}`;
  }
}

async function finalize() {
  const st = $("save-status");
  if (!window.confirm("Finalize this date's Trial Balance? It cannot be edited afterwards.")) return;
  try {
    render(await api.post(`/daily-trial-balance/${$("tb-date").value}/finalize`));
    st.className = "status-line ok";
    st.textContent = "Finalized.";
  } catch (err) {
    st.className = "status-line err";
    st.textContent = `Finalize failed — ${err.message || err}`;
  }
}

async function init() {
  if (!getToken()) {
    window.location.href = "../../index.html";
    return;
  }
  let me;
  try {
    me = await api.me();
  } catch {
    window.location.href = "../../index.html";
    return;
  }
  $("who").textContent = `${me.full_name} (${me.role})`;
  $("tb-date").value = new Date().toISOString().slice(0, 10);
  $("load-btn").addEventListener("click", load);
  $("save-btn").addEventListener("click", save);
  $("finalize-btn").addEventListener("click", finalize);
  await load();
}

init();
