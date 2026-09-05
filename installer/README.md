# installer/

Packaging + first-run setup for the SVR IOCL Station desktop app. The output is a
single NSIS `.exe` that needs **no Python and no Node** on the target PC.

## Build

```powershell
# from the repo root, after `npm ci` in frontend/
installer\build-all.ps1
```

That runs two steps:

1. **`backend/packaging/build-backend.ps1`** — PyInstaller one-dir freeze →
   `backend/packaging/dist/svr-backend/`, containing three console exes that share
   one runtime (`MERGE` in `svr_backend.spec`):

   | exe | role |
   |---|---|
   | `svr-backend.exe` | CLI: `migrate` / `serve` / `scheduler` / `gen-key` |
   | `svr-backend-service.exe` | `SVR-IOCL-Backend` Windows Service host |
   | `svr-scheduler-service.exe` | `SVR-IOCL-Scheduler` Windows Service host |

2. **`npm run dist`** (electron-builder, NSIS) — bundles that folder as
   `resources/backend/` (`extraResources`), ships `first-run.ps1` + `uninstall.ps1`
   to `<INSTDIR>\installer\` (`extraFiles`), and wires the install/uninstall hooks
   from `frontend/build/installer.nsh`. Output: `installer/output/SVR-IOCL-Station-Setup-*.exe`.

CI's `build` job (`.github/workflows/ci.yml`) runs the same two steps and uploads
the `.exe` artifact.

## Releasing a new version

The version number is kept by hand in three places — bump all three together:

| File | Field |
|---|---|
| `frontend/package.json` | `"version"` |
| `backend/pyproject.toml` | `[project] version` |
| `backend/src/svr_backend/__init__.py` | `__version__` |

Then:

```powershell
cd backend; .venv\Scripts\python -m ruff check .; .venv\Scripts\python -m pytest -q; cd ..
cd frontend; npm run lint; npx playwright test; cd ..
installer\build-all.ps1
git add -A && git commit -m "release: vX.Y.Z"
git tag vX.Y.Z && git push --tags
```

The installer filename tracks `frontend/package.json`'s version
(`SVR-IOCL-Station-Setup-<version>.exe`). `/health` returns
`backend/__init__.py`'s `__version__`, so keeping the three in step is what makes
the running backend, the API, and the installer all report the same number.

## What the installer does on the target

`perMachine` + assisted (not one-click), so it runs elevated. On install,
`installer.nsh` → `customInstall` runs **`first-run.ps1`**:

1. Creates the data + per-component log tree under `C:\ProgramData\SVR-IOCL`
   (SDD 14.3).
2. Persists `SVR_DATA_DIR` / `SVR_DB_PATH` / `SVR_LOG_DIR` as **machine**
   environment variables (so the SCM-started services see them), and generates
   `SVR_FIELD_KEY` (Fernet, SDD 13.3) once if unset.
3. Applies SQLite migrations (`svr-backend.exe migrate`).
4. Registers **both Windows Services** `--startup auto` and starts them.
5. Adds the Electron frontend as a per-user Startup-folder shortcut (SDD 19
   item 23 — not a service).

On uninstall, `customUnInstall` runs **`uninstall.ps1`**: stops + deletes both
services and removes the Startup shortcut. It deliberately **keeps
`C:\ProgramData\SVR-IOCL`** (DB, nightly backups, logs) and the machine env vars
so a reinstall resumes cleanly.

## Service model (SDD §7.1 / ADR-2)

| Service | Runs | Startup |
|---|---|---|
| `SVR-IOCL-Backend` | uvicorn loopback API + calc engine + RBAC + audit | Automatic |
| `SVR-IOCL-Scheduler` | APScheduler 23:59 IST carry-forward + daily SQLite backup | Automatic |

SQLite gets no service (a file, opened in-process). Tesseract gets no service (a
library invoked on demand).

## Still follow-on (not in this packaging pass)

1. **Bundle Tesseract OCR** (SDD ADR-6) — folder + `SVR_TESSERACT_PATH` config
   key; lands with the OCR module (not started).
2. **Authenticode code-signing** of the exe + installer, and auto-update.
3. **Clean-VM validation** — install on a fresh Windows 11 VM: both services
   `Automatic` + `Running` in `services.msc`; `C:\ProgramData\SVR-IOCL\logs\`
   populated; `svr.sqlite` migrated; the Startup shortcut opens the app and it
   reaches the backend; reboot re-launches everything; uninstall removes the
   services but keeps the data tree.
