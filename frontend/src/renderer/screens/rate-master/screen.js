// Rate Master screen (SDD 5.11 / 9). Manager views; only the Owner can edit and
// push. Each push appends a new effective-dated row (append-only versioning);
// Section 2 is the running change log from GET /rate-master/history.

import { api, getToken } from "../../lib/api.js";

const $ = (id) => document.getElementById(id);
const money = (n) => (n === null || n === undefined ? "" : String(n));

let me = null;
const FUEL_UNIT = { HS: "Litre", MS: "Litre" };

function canEdit() {
  return me && me.role === "Owner";
}

function renderCurrent(rows) {
  const body = $("rate-rows");
  body.innerHTML = "";
  for (const r of rows) {
    const tr = document.createElement("tr");
    tr.dataset.itemKey = r.item_key;
    tr.dataset.currentSell = r.sell_rate;
    tr.innerHTML =
      `<td>${r.item_label}</td>` +
      `<td><input disabled value="${money(r.buy_rate)}"></td>` +
      `<td><input disabled value="${money(r.sell_rate)}"></td>` +
      `<td><input class="new-buy" ${canEdit() ? "" : "disabled"} placeholder="—"></td>` +
      `<td><input class="new-sell" ${canEdit() ? "" : "disabled"} placeholder="—"></td>` +
      `<td>${FUEL_UNIT[r.item_key] || "Unit"}</td>`;
    body.appendChild(tr);
  }
}

function renderHistory(rows) {
  const body = $("history-rows");
  body.innerHTML = "";
  for (const h of rows) {
    const tr = document.createElement("tr");
    tr.innerHTML =
      `<td>${h.effective_date}</td><td>${h.item_label}</td>` +
      `<td>${money(h.prev_sell_rate)}</td><td>${money(h.sell_rate)}</td>` +
      `<td>${money(h.buy_rate)}</td><td>${h.updated_by || ""}</td>`;
    body.appendChild(tr);
  }
}

async function load() {
  const [current, history] = await Promise.all([
    api.get("/rate-master/current"),
    api.get("/rate-master/history"),
  ]);
  renderCurrent(current);
  renderHistory(history);
}

function collectUpdates() {
  const updates = [];
  for (const tr of document.querySelectorAll("#rate-rows tr")) {
    const newSell = tr.querySelector(".new-sell").value.trim();
    const newBuy = tr.querySelector(".new-buy").value.trim();
    if (!newSell && !newBuy) continue;
    updates.push({
      item_key: tr.dataset.itemKey,
      // sell_rate is required by the API; keep the current one if only buy changed.
      sell_rate: newSell ? Number(newSell) : Number(tr.dataset.currentSell),
      buy_rate: newBuy ? Number(newBuy) : null,
      effective_date: $("effective-date").value || null,
    });
  }
  return updates;
}

async function push() {
  const st = $("push-status");
  const updates = collectUpdates();
  if (!updates.length) {
    st.className = "status-line err";
    st.textContent = "Enter at least one new rate.";
    return;
  }
  st.className = "status-line";
  st.textContent = "Pushing…";
  try {
    await api.put("/rate-master/", updates);
    await load();
    st.className = "status-line ok";
    st.textContent = `Pushed ${updates.length} rate change(s).`;
  } catch (err) {
    st.className = "status-line err";
    st.textContent = `Push failed — ${err.message || err}`;
  }
}

async function init() {
  if (!getToken()) {
    window.location.href = "../../index.html";
    return;
  }
  try {
    me = await api.me();
  } catch {
    window.location.href = "../../index.html";
    return;
  }
  $("who").textContent = `${me.full_name} (${me.role})`;
  $("effective-date").value = new Date().toISOString().slice(0, 10);

  if (!canEdit()) {
    $("role-tag").textContent = "View Only";
    $("push-btn").style.display = "none";
    $("effective-date").disabled = true;
  }

  $("push-btn").addEventListener("click", push);
  await load();
}

init();
