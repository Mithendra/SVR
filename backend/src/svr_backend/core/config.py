"""Runtime configuration.

Every value has a safe local-dev default and can be overridden by an ``SVR_``-prefixed
environment variable (e.g. ``SVR_DB_PATH``, ``SVR_API_PORT``). On the deployment
target these are set by the installer's first-run step (see installer/ and SDD 14).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo-local default data dir for development. Production uses C:\ProgramData\SVR-IOCL
# (SDD 14.3) supplied via SVR_DATA_DIR.
_DEFAULT_DATA_DIR = Path(__file__).resolve().parents[4] / "local"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SVR_", env_file=".env", extra="ignore")

    data_dir: Path = Field(default=_DEFAULT_DATA_DIR)
    db_path: Path | None = Field(default=None)
    log_dir: Path | None = Field(default=None)

    # Loopback only - the backend never binds a routable interface (SDD 7.2).
    api_host: str = "127.0.0.1"
    api_port: int = 8756

    # Carry-forward job (SDD 7.7). Explicit, never the host machine's tz.
    scheduler_timezone: str = "Asia/Kolkata"
    carry_forward_hour: int = 23
    carry_forward_minute: int = 59

    session_ttl_minutes: int = 12 * 60

    # Fernet key (urlsafe-base64, 32 bytes) for encrypting sensitive fields at rest
    # (SDD 13.3 - employee bank account / IFSC). Set SVR_FIELD_KEY in production;
    # an insecure dev key is used with a warning when unset.
    field_key: str | None = None

    def resolved_db_path(self) -> Path:
        return self.db_path or (self.data_dir / "svr.sqlite")

    def resolved_log_dir(self) -> Path:
        return self.log_dir or (self.data_dir / "logs")


@lru_cache
def get_settings() -> Settings:
    return Settings()
