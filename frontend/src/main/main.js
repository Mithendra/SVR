"use strict";

// SVR-IOCL Frontend - Electron main process. One window, loads the renderer shell.
// The backend base URL is passed to the renderer through the context-isolated
// preload bridge; the renderer never gets Node access (SDD 4.3 / 6).

const { app, BrowserWindow, Menu } = require("electron");
const path = require("path");

const API_BASE = process.env.SVR_API_BASE || "http://127.0.0.1:8756";

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

  win.loadFile(path.join(__dirname, "..", "renderer", "index.html"));
}

app.whenReady().then(() => {
  createWindow();
  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
