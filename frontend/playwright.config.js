"use strict";

const { defineConfig } = require("@playwright/test");
const { staticBase } = require("./tests/_helpers");

module.exports = defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  timeout: 30000,
  // One retry absorbs the occasional cold-start / shared-DB race in the e2e suite.
  retries: 1,
  reporter: [["list"]],
  globalSetup: "./tests/global-setup.js",
  use: {
    baseURL: staticBase,
    trace: "retain-on-failure",
  },
});
