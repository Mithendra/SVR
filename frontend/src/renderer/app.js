// Shell: login, then a role-filtered nav. Sales sees only Daily Sales Entry
// (SDD 6.1). The rest of the 11 modules are follow-on work.

import { api, apiBase, getToken, setToken } from "./lib/api.js";

const MODULES = [
  { key: "daily-sales-entry", label: "Daily Sales Entry", href: "screens/daily-sales-entry/index.html", roles: ["Sales", "Manager", "Owner"] },
  { key: "daily-sales-summary", label: "Daily Sales Summary", href: "screens/daily-sales-summary/index.html", roles: ["Sales", "Manager", "Owner"] },
  { key: "rate-master", label: "Rate Master", href: "screens/rate-master/index.html", roles: ["Manager", "Owner"] },
  { key: "inventory-tracking", label: "Inventory Tracking", href: "screens/inventory-tracking/index.html", roles: ["Manager", "Owner"] },
  { key: "daily-trial-balance", label: "Daily Trial Balance", href: "#", roles: ["Manager", "Owner"], todo: true },
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
