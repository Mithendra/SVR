"""Per-component log files (SDD 14.3) - one file per component, never a shared log,
so a failed service is diagnosable on its own.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from svr_backend.core.config import get_settings

# SDD 14.3 - the six component log files. Deferred components are listed now so the
# tree is created up front.
COMPONENT_LOGS = {
    "backend": "backend-service.log",
    "scheduler": "scheduler.log",
    "database": "database.log",
    "frontend": "frontend.log",
    "email": "email-integration.log",
    "ocr": "ocr-processing.log",
}


def configure(component: str, level: int = logging.INFO) -> logging.Logger:
    log_dir = get_settings().resolved_log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    filename = COMPONENT_LOGS.get(component, f"{component}.log")

    handler = RotatingFileHandler(
        log_dir / filename, maxBytes=5_000_000, backupCount=5, encoding="utf-8"
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    )
    root = logging.getLogger()
    root.setLevel(level)
    # Avoid duplicate handlers if called twice in one process.
    if not any(isinstance(h, RotatingFileHandler) for h in root.handlers):
        root.addHandler(handler)
    root.addHandler(logging.StreamHandler())
    return logging.getLogger(f"svr.{component}")
