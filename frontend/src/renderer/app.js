// Shell: login, then a role-filtered nav. Sales sees only Daily Sales Entry
// (SDD 6.1). The rest of the 11 modules are follow-on work.

import { api, apiBase, getToken, setToken } from "./lib/api.js";

const MODULES = [
  { key: "daily-sales-entry", label: "Daily Sales Entry", href: "screens/daily-sales-entry/index.html", roles: ["Sales", "Manager", "Owner"] },
  { key: "daily-sales-summary", label: "Daily Sales Summary", href: "screens/daily-sales-summary/index.html", roles: ["Sales", "Manager", "Owner"] },
  { key: "rate-master", label: "Rate Master", href: "screens/rate-master/index.html", roles: ["Manager", "Owner"] },
  { key: "inventory-tracking", label: "Inventory Tracking", href: "screens/inventory-tracking/index.html", roles: ["Manager", "Owner"] },
  { key: "manage-users", label: "Manage Users", href: "screens/manage-users/index.html", roles: ["Manager", "Owner"] },
  { key: "credit-remittance-master", label: "Credit / Remittance Master", href: "screens/credit-remittance-master/index.html", roles: ["Manager", "Owner"] },
  { key: "monthly-expenses", label: "Monthly Expenses", href: "screens/monthly-expenses/index.html", roles: ["Manager", "Owner"] },
  { key: "employee-master", label: "Employee Master", href: "screens/employee-master/index.html", roles: ["Manager", "Owner"] },
  { key: "payment-receipt", label: "Payment Receipt", href: "screens/payment-receipt/index.html", roles: ["Sales", "Manager", "Owner"] },
  { key: "yearly-sales-report", label: "Yearly Sales Report", href: "screens/yearly-sales-report/index.html", roles: ["Manager", "Owner"] },
  { key: "daily-trial-balance", label: "Daily Trial Balance", href: "screens/daily-trial-balance/index.html", roles: ["Manager", "Owner"] },
];

const loginView = document.getElementById("login-view");
const navView = document.getElementById("nav-view");
const loginError = document.getElementById("login-error");

function withApiBase(href) {
  const sep = href.includes("?") ? "&" : "?";
  return `${href}${sep}apiBase=${encodeURIComponent(apiBase)}`;
}

function renderNav(me) {
  document.getElementById("who").textContent = `${me.full_name} (${me.role})`;
  const ul = document.getElementById("nav-links");
  ul.innerHTML = "";
  for (const mod of MODULES) {
    if (!mod.roles.includes(me.role)) continue;
    const li = document.createElement("li");
    if (mod.todo) {
      li.textContent = `${mod.label} — coming soon`;
    } else {
      const a = document.createElement("a");
      a.className = "btn";
      a.textContent = mod.label;
      a.href = withApiBase(mod.href);
      a.dataset.module = mod.key;
      li.appendChild(a);
    }
    ul.appendChild(li);
  }
  loginView.hidden = true;
  navView.hidden = false;
}

async function showSignedIn() {
  const me = await api.me();
  renderNav(me);
}

document.getElementById("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  loginError.textContent = "";
  try {
    await api.login(
      document.getElementById("login-name").value.trim(),
      document.getElementById("password").value
    );
    await showSignedIn();
  } catch (err) {
    loginError.textContent = err.status === 401 ? "Invalid login name or password." : String(err.message || err);
  }
});

document.getElementById("forgot-link").addEventListener("click", async (e) => {
  e.preventDefault();
  const status = document.getElementById("forgot-status");
  const id = window.prompt("Enter your login name or email:");
  if (!id) return;
  try {
    const out = await api.post("/auth/password-reset/request", { identifier: id.trim() });
    status.style.color = "#157347";
    status.textContent = out.detail || "If that account exists, a reset link has been emailed.";
    // Dev email backends echo the link so you can complete the flow without a mailbox.
    if (out.dev_reset_link) window.location.href = out.dev_reset_link;
  } catch (err) {
    status.style.color = "";
    status.textContent = err.message || String(err);
  }
});

document.getElementById("logout").addEventListener("click", async () => {
  try {
    await api.post("/auth/logout");
  } catch {
    /* ignore - clearing locally regardless */
  }
  setToken(null);
  navView.hidden = true;
  loginView.hidden = false;
});

// Resume an existing window session (set by a prior login before navigating).
if (getToken()) {
  showSignedIn().catch(() => setToken(null));
}
