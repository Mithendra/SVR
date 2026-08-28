"""SVR-IOCL Scheduler Service - runs the 23:59 IST carry-forward job and the daily
SQLite backup as a Windows Service (SDD 7.7 / 8.4).

Install (elevated)::

    python -m svr_backend.services.scheduler_service --startup auto install
    python -m svr_backend.services.scheduler_service start
"""

from __future__ import annotations

import sys

try:
    import servicemanager
    import win32event
    import win32service
    import win32serviceutil
except ImportError as exc:  # pragma: no cover - only meaningful on Windows
    raise SystemExit(
        "pywin32 is required. Install with: pip install svr-backend[win]"
    ) from exc

from svr_backend.scheduler import build_scheduler, startup_catch_up


class SvrSchedulerService(win32serviceutil.ServiceFramework):
    _svc_name_ = "SVR-IOCL-Scheduler"
    _svc_display_name_ = "SVR-IOCL Scheduler Service"
    _svc_description_ = "SVR - nightly 23:59 IST reading carry-forward and daily database backup."

    def __init__(self, args):
        super().__init__(args)
        self._stop_evt = win32event.CreateEvent(None, 0, 0, None)
        self._sched = None

    def SvcStop(self):  # noqa: N802
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        if self._sched is not None:
            self._sched.shutdown(wait=False)
        win32event.SetEvent(self._stop_evt)

    def SvcDoRun(self):  # noqa: N802
        try:
            from svr_backend.logging_setup import configure

            configure("scheduler")
        except Exception:
            pass
        startup_catch_up()
        self._sched = build_scheduler()
        self._sched.start()
        win32event.WaitForSingleObject(self._stop_evt, win32event.INFINITE)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(SvrSchedulerService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(SvrSchedulerService)
