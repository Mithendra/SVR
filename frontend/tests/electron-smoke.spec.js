"use strict";

const path = require("path");
const { test, expect, _electron: electron } = require("@playwright/test");
const { apiBase } = require("./_helpers");

test("Electron app launches and renders the shell", async () => {
  // Some shells export ELECTRON_RUN_AS_NODE=1, which makes electron.exe behave as
  // plain Node and reject Chromium flags ("bad option: --remote-debugging-port").
  // Strip it so the real Electron runtime starts.
  const env = { ...process.env, SVR_API_BASE: apiBase };
  delete env.ELECTRON_RUN_AS_NODE;

  const app = await electron.launch({
    args: [path.join(__dirname, "..", "src", "main", "main.js")],
    env,
  });
  const window = await app.firstWindow();
  await expect(window.locator("#login-view")).toBeVisible();
  await expect(window).toHaveTitle(/SVR/);

  // The preload bridge is the only thing exposed to the renderer.
  const base = await window.evaluate(() => window.svr && window.svr.apiBase);
  expect(base).toBe(apiBase);

  await app.close();
});
