// Shell: login, then a role-filtered nav. Sales sees only Daily Sales Entry
// and Payment Receipt (SDD 6.1). The rest of the 11 modules are follow-on work.

import { api, apiBase, getToken, setToken } from "./lib/api.js";

// Order confirmed with the client (BRD session-update entry 106). Manage Users
// sits in its own "Admin" group below the daily-operations modules - grouped
// visually only, RBAC is unchanged (Manager and Owner both see it, same as before).
const MODULES = [
  { key: "daily-sales-entry", label: "Daily Sales Entry", href: "screens/daily-sales-entry/index.html", roles: ["Sales", "Manager", "Owner"] },
  { key: "daily-sales-summary", label: "Daily Sales Summary", href: "screens/daily-sales-summary/index.html", roles: ["Sales", "Manager", "Owner"] },
  { key: "daily-trial-balance", label: "Daily Trial Balance", href: "screens/daily-trial-balance/index.html", roles: ["Manager", "Owner"] },
  { key: "credit-remittance-master", label: "Credit / Remittance Master", href: "screens/credit-remittance-master/index.html", roles: ["Manager", "Owner"] },
  { key: "payment-receipt", label: "Payment Receipt", href: "screens/payment-receipt/index.html", roles: ["Sales", "Manager", "Owner"] },
  { key: "inventory-tracking", label: "Inventory Tracking", href: "screens/inventory-tracking/index.html", roles: ["Manager", "Owner"] },
  { key: "rate-master", label: "Rate Master", href: "screens/rate-master/index.html", roles: ["Manager", "Owner"] },
  { key: "monthly-expenses", label: "Monthly Expenses", href: "screens/monthly-expenses/index.html", roles: ["Manager", "Owner"] },
  { key: "employee-master", label: "Employee Master", href: "screens/employee-master/index.html", roles: ["Manager", "Owner"] },
  { key: "yearly-sales-report", label: "Yearly Sales Report", href: "screens/yearly-sales-report/index.html", roles: ["Manager", "Owner"] },
];

// Manage Users renders after a divider, in its own "Admin" group - kept out of
// MODULES above so the divider only appears when this item actually will.
const ADMIN_MODULE = {
  key: "manage-users",
  label: "Manage Users",
  href: "screens/manage-users/index.html",
  roles: ["Manager", "Owner"],
};

// One consistent icon style: 24px viewBox, stroke-based, currentColor so it
// inherits each nav link's text color (active/inactive) automatically.
const ICONS = {
  "daily-sales-entry": '<rect x="6" y="3" width="12" height="18" rx="2"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="9" y1="12" x2="15" y2="12"/><line x1="9" y1="16" x2="13" y2="16"/>',
  "daily-sales-summary": '<line x1="4" y1="20" x2="20" y2="20"/><rect x="6" y="13" width="3" height="7"/><rect x="11" y="9" width="3" height="11"/><rect x="16" y="5" width="3" height="15"/>',
  "daily-trial-balance": '<line x1="12" y1="4" x2="12" y2="20"/><line x1="5" y1="8" x2="19" y2="8"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="12" r="3"/><line x1="8" y1="20" x2="16" y2="20"/>',
  "credit-remittance-master": '<rect x="3" y="6" width="18" height="13" rx="2"/><line x1="3" y1="10" x2="21" y2="10"/><line x1="6" y1="15" x2="10" y2="15"/>',
  "payment-receipt": '<path d="M6 3h12v16l-2-1.2-2 1.2-2-1.2-2 1.2-2-1.2-2 1.2Z"/><line x1="9" y1="7.5" x2="15" y2="7.5"/><path d="M9 12.5l1.5 1.5 3-3"/>',
  "inventory-tracking": '<path d="M12 3 20 7v10l-8 4-8-4V7Z"/><path d="M4 7l8 4 8-4"/><line x1="12" y1="11" x2="12" y2="21"/>',
  "rate-master": '<path d="M11 3H5a2 2 0 0 0-2 2v6l10 10 8-8L11 3Z"/><circle cx="7.5" cy="7.5" r="1.5"/>',
  "monthly-expenses": '<path d="M3 7a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"/><path d="M3 10h16"/><circle cx="16" cy="14" r="1.3"/>',
  "employee-master": '<rect x="5" y="3" width="14" height="18" rx="2"/><circle cx="12" cy="10" r="2.6"/><path d="M8 17c.7-2 2-3 4-3s3.3 1 4 3"/>',
  "yearly-sales-report": '<rect x="3" y="5" width="18" height="15" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="8" y1="3" x2="8" y2="7"/><line x1="16" y1="3" x2="16" y2="7"/><path d="M6.5 16l3-3 2.5 2 4.5-5"/>',
  "manage-users": '<circle cx="9" cy="8" r="3"/><path d="M3 20c0-3.3 2.7-5.5 6-5.5s6 2.2 6 5.5"/><circle cx="17" cy="9" r="2.4"/><path d="M15.5 14.2c2.6.3 4.5 2.2 4.5 5.3"/>',
};

const loginView = document.getElementById("login-view");
const navView = document.getElementById("nav-view");
const loginError = document.getElementById("login-error");

function withApiBase(href) {
  const sep = href.includes("?") ? "&" : "?";
  return `${href}${sep}apiBase=${encodeURIComponent(apiBase)}`;
}

function navLink(mod) {
  const a = document.createElement("a");
  a.className = "nav-item";
  a.href = withApiBase(mod.href);
  a.dataset.module = mod.key;
  a.innerHTML = `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[mod.key] || ""}</svg><span>${mod.label}</span>`;
  return a;
}

function renderNav(me) {
  document.getElementById("who").textContent = `${me.full_name} (${me.role})`;
  const container = document.getElementById("nav-links");
  container.innerHTML = "";
  for (const mod of MODULES) {
    if (!mod.roles.includes(me.role)) continue;
    container.appendChild(navLink(mod));
  }
  if (ADMIN_MODULE.roles.includes(me.role)) {
    const divider = document.createElement("div");
    divider.className = "nav-divider";
    container.appendChild(divider);
    const label = document.createElement("div");
    label.className = "nav-group-label";
    label.textContent = "Admin";
    container.appendChild(label);
    container.appendChild(navLink(ADMIN_MODULE));
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
