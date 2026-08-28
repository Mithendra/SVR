"use strict";

// The only bridge into the renderer. Exposes the backend base URL (from a
// --svr-api-base=... argument set in main.js) and nothing else.

const { contextBridge } = require("electron");

function readApiBase() {
  const arg = process.argv.find((a) => a.startsWith("--svr-api-base="));
  return arg ? arg.slice("--svr-api-base=".length) : "http://127.0.0.1:8756";
}

contextBridge.exposeInMainWorld("svr", {
  apiBase: readApiBase(),
  isElectron: true,
});
