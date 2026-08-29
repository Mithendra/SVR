"use strict";

// SVR-IOCL Frontend - Electron main process. One window, loads the renderer shell.
// The backend base URL is passed to the renderer through the context-isolated
// preload bridge; the renderer never gets Node access (SDD 4.3 / 6).
//
// On a deployed machine the backend runs as the SVR-IOCL-Backend Windows Service,
// so /health answers immediately. If it does not (service still starting, or
// stopped), and this is a packaged build, fall back to spawning the bundled
// resources/backend/svr-backend.exe. In dev (`npm start`) there is no bundled exe;
// a dev backend on :8756 is assumed and the renderer loads regardless.

const { app, BrowserWindow, Menu } = require("electron");
const path = require("path");
const http = require("http");
const fs = require("fs");
const { spawn } = require("child_process");

const API_BASE = process.env.SVR_API_BASE || "http://127.0.0.1:8756";
const HEALTH_URL = `${API_BASE}/health`;
const STARTUP_TIMEOUT_MS = 20000;
const POLL_INTERVAL_MS = 500;

let backendProc = null;

function pingHealth() {
  return new Promise((resolve) => {
    const req = http.get(HEALTH_URL, { timeout: 2000 }, (res) => {
      res.resume();
      resolve(res.statusCode === 200);
    });
    req.on("error", () => resolve(false));
    req.on("timeout", () => {
      req.destroy();
      resolve(false);
    });
  });
}

function bundledBackendExe() {
  // Packaged layout: <app>/resources/backend/svr-backend.exe (extraResources).
  const exe = path.join(process.resourcesPath, "backend", "svr-backend.exe");
  return fs.existsSync(exe) ? exe : null;
}

function startBundledBackend() {
  const exe = bundledBackendExe();
  if (!exe || backendProc) return;
  backendProc = spawn(exe, ["serve"], { stdio: "ignore", windowsHide: true });
  backendProc.on("exit", () => {
    backendProc = null;
  });
}

function stopBundledBackend() {
  if (!backendProc) return;
  try {
    backendProc.kill();
  } catch {
    // process already gone
  }
  backendProc = null;
}

async function waitForBackend() {
  const deadline = Date.now() + STARTUP_TIMEOUT_MS;
  let triedSpawn = false;
  while (Date.now() < deadline) {
    if (await pingHealth()) return true;
    if (!triedSpawn) {
      triedSpawn = true;
      startBundledBackend(); // no-op in dev / when already running
    }
    await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
  }
  return pingHealth();
}

const SPLASH_HTML = `<!doctype html><meta charset="utf-8">
<style>
  html,body{height:100%;margin:0}
  body{display:flex;align-items:center;justify-content:center;
       font:14px 'Segoe UI',Arial,sans-serif;background:#f4f6fb;color:#00246e}
  .box{text-align:center}
  .dot{display:inline-block;width:8px;height:8px;margin:0 2px;border-radius:50%;
       background:#0033a0;animation:b 1s infinite alternate}
  .dot:nth-child(2){animation-delay:.2s}.dot:nth-child(3){animation-delay:.4s}
  @keyframes b{to{opacity:.2}}
</style>
<div class="box">
  <div style="font-weight:700;margin-bottom:10px">SVR IOCL Station</div>
  <div>Starting&nbsp;<span class="dot"></span><span class="dot"></span><span class="dot"></span></div>
</div>`;

function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 900,
    title: "SVR IOCL Station",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      additionalArguments: [`--svr-api-base=${API_BASE}`],
    },
  });

  Menu.setApplicationMenu(
    Menu.buildFromTemplate([
      { role: "fileMenu" },
      { role: "editMenu" },
      { role: "viewMenu" },
      { role: "windowMenu" },
    ])
  );

  win.loadURL("data:text/html;charset=utf-8," + encodeURIComponent(SPLASH_HTML));

  waitForBackend().then(() => {
    // Load the app either way - if the backend never came up the renderer shows
    // its own connection error, which is clearer than a blank splash.
    if (!win.isDestroyed()) {
      win.loadFile(path.join(__dirname, "..", "renderer", "index.html"));
    }
  });

  return win;
}

app.whenReady().then(() => {
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  stopBundledBackend();
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", stopBundledBackend);
