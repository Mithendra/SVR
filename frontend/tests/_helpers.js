"use strict";

const path = require("path");

const BACKEND_PORT = 8799;
const STATIC_PORT = 5599;

const REPO_ROOT = path.resolve(__dirname, "..", "..");
const RENDERER_DIR = path.resolve(__dirname, "..", "src", "renderer");

// Backend console scripts from the dev venv; override with SVR_BACKEND_BIN in CI.
const BACKEND_BIN =
  process.env.SVR_BACKEND_BIN || path.join(REPO_ROOT, "backend", ".venv", "Scripts");

const backendExe = (name) => path.join(BACKEND_BIN, process.platform === "win32" ? `${name}.exe` : name);

module.exports = {
  BACKEND_PORT,
  STATIC_PORT,
  REPO_ROOT,
  RENDERER_DIR,
  BACKEND_BIN,
  backendExe,
  apiBase: `http://127.0.0.1:${BACKEND_PORT}`,
  staticBase: `http://127.0.0.1:${STATIC_PORT}`,
};
