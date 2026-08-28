"use strict";

const { defineConfig } = require("@playwright/test");
const { staticBase } = require("./tests/_helpers");

module.exports = defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  timeout: 30000,
  reporter: [["list"]],
  globalSetup: "./tests/global-setup.js",
  use: {
    baseURL: staticBase,
    trace: "retain-on-failure",
  },
});
