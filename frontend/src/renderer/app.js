// Shell: login, then a role-filtered nav. Sales sees only Daily Sales Entry
// and Payment Receipt (SDD 6.1). The module list + sidebar builder live in
// lib/nav.js so the per-screen shell renders an identical sidebar.

import { api, getToken, setToken } from "./lib/api.js";
import { buildNav } from "./lib/nav.js";

const loginView = document.getElementById("login-view");
const navView = document.getElementById("nav-view");
const loginError = document.getElementById("login-error");

function renderNav(me) {
  document.getElementById("who").textContent = `${me.full_name} (${me.role})`;
  buildNav(document.getElementById("nav-links"), me.role);
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
