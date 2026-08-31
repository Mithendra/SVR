"""SVR-IOCL Backend Service - hosts the uvicorn loopback API as a Windows Service.

Install (elevated), on the deployment target::

    python -m svr_backend.services.backend_service --startup auto install
    python -m svr_backend.services.backend_service start

Requires the ``win`` extra (``pip install svr-backend[win]``).
"""

from __future__ import annotations

import sys
import threading

try:
    import servicemanager
    import win32serviceutil
    from win32service import SERVICE_STOP_PENDING
except ImportError as exc:  # pragma: no cover - only meaningful on Windows
    raise SystemExit(
        "pywin32 is required. Install with: pip install svr-backend[win]"
    ) from exc

import uvicorn

from svr_backend.core.config import get_settings


class _Server(uvicorn.Server):
    def install_signal_handlers(self) -> None:  # service controls lifecycle, not signals
        pass


class SvrBackendService(win32serviceutil.ServiceFramework):
    _svc_name_ = "SVR-IOCL-Backend"
    _svc_display_name_ = "SVR-IOCL Backend Service"
    _svc_description_ = "SVR Indian Oil Service Station - API, calculation engine, RBAC, audit."

    def __init__(self, args):
        super().__init__(args)
        settings = get_settings()
        config = uvicorn.Config(
            "svr_backend.app:app",
            host=settings.api_host,
            port=settings.api_port,
            log_level="info",
            # log_config=None: a Windows Service has no console, so uvicorn's
            # default logging dictConfig (StreamHandlers on sys.stdout/stderr,
            # which are absent) fails on config.load(). None skips it and lets
            # uvicorn's records propagate to the RotatingFileHandler that
            # logging_setup.configure("backend") put on the root logger.
            log_config=None,
        )
        self._server = _Server(config)
        self._thread = threading.Thread(target=self._server.run, daemon=True)

    def SvcStop(self):  # noqa: N802 - pywin32 API
        self.ReportServiceStatus(SERVICE_STOP_PENDING)
        self._server.should_exit = True

    def SvcDoRun(self):  # noqa: N802 - pywin32 API
        try:
            from svr_backend.logging_setup import configure

            configure("backend")
        except Exception:
            pass
        self._thread.start()
        self._thread.join()


if __name__ == "__main__":
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(SvrBackendService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(SvrBackendService)
