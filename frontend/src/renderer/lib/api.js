// Loopback API client. Base URL resolution order:
//   1. window.svr.apiBase  (Electron preload bridge)
//   2. ?apiBase=...         (Playwright page-mode / dev)
//   3. http://127.0.0.1:8756 (default from SDD config)

function resolveBase() {
  if (window.svr && window.svr.apiBase) return window.svr.apiBase;
  const q = new URLSearchParams(window.location.search).get("apiBase");
  return q || "http://127.0.0.1:8756";
}

export const apiBase = resolveBase();

// Session token lives in sessionStorage: scoped to this window, cleared when the
// app closes, and shared across the shell -> screen page navigation. Not
// localStorage - nothing about a login should outlive the window (SDD 13.1).
const TOKEN_KEY = "svr.session.token";
let sessionToken = null;
try {
  sessionToken = window.sessionStorage.getItem(TOKEN_KEY);
} catch {
  sessionToken = null;
}

export function setToken(token) {
  sessionToken = token;
  try {
    if (token) window.sessionStorage.setItem(TOKEN_KEY, token);
    else window.sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    /* sessionStorage unavailable - in-memory only */
  }
}

export function getToken() {
  return sessionToken;
}

async function request(method, path, body) {
  const headers = { "Content-Type": "application/json" };
  if (sessionToken) headers.Authorization = `Bearer ${sessionToken}`;

  const res = await fetch(apiBase + path, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });

  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const detail = data && data.detail ? data.detail : res.statusText;
    const err = new Error(`${method} ${path} -> ${res.status}: ${detail}`);
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

export const api = {
  get: (p) => request("GET", p),
  post: (p, b) => request("POST", p, b),
  put: (p, b) => request("PUT", p, b),
  del: (p) => request("DELETE", p),

  async login(loginName, password) {
    const out = await request("POST", "/auth/login", {
      login_name: loginName,
      password,
    });
    setToken(out.token);
    return out;
  },
  me: () => request("GET", "/auth/me"),
};
