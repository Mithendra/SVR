# installer/

Packaging + first-run setup for the SVR IOCL Station desktop app.

## What's here now (scaffold)

- **electron-builder config** — currently inline in `frontend/package.json` under
  `build` (NSIS target, output to `installer/output/`). `npm run dist` in
  `frontend/` produces the `.exe`; CI's `build` job runs it and uploads the
  artifact.
- **`first-run.ps1`** — the elevated post-install step: applies DB migrations,
  creates the per-component log tree, registers the two Windows Services
  (`SVR-IOCL-Backend`, `SVR-IOCL-Scheduler`) with `Automatic` start, and adds the
  Electron frontend as a per-user Startup-folder shortcut (SDD §19 item 23 — not a
  service).

## Follow-on work (not done this session)

1. **Freeze the Python backend** with PyInstaller (one-dir) and bundle it +
   the SQLite DLL into `extraResources` so the target PC needs no Python.
2. **Bundle Tesseract OCR** (SDD ADR-6) — folder + `SVR_TESSERACT_PATH` config
   key; wire it when the OCR phase lands.
3. Have the NSIS `include`/`installerScript` invoke `first-run.ps1` elevated on
   install and a matching uninstall script that removes the services.
4. Validate on a clean Windows VM: both services `Automatic` + `Running` in
   `services.msc`; `C:\ProgramData\SVR-IOCL\logs\` populated; the Startup shortcut
   opens the app.

## Service model (SDD §7.1 / ADR-2)

| Service | Runs | Startup |
|---|---|---|
| `SVR-IOCL-Backend` | uvicorn loopback API + calc engine + RBAC + audit | Automatic |
| `SVR-IOCL-Scheduler` | APScheduler 23:59 IST carry-forward + daily SQLite backup | Automatic |

SQLite gets no service (a file, opened in-process). Tesseract gets no service (a
library invoked on demand).
