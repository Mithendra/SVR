"""Email delivery (SDD 7.6). Three backends, chosen by ``SVR_EMAIL_BACKEND``:

* ``memory`` (default) - append to an in-process list; nothing leaves the machine.
  Handy for tests and for dev, where the reset link is also echoed in the API
  response.
* ``file`` - write each message as a ``.txt`` file under ``data_dir/outbox``.
* ``smtp`` - send for real via the ``smtp_*`` settings (recommended prod default
  for this ~10-user station).
"""

from __future__ import annotations

import logging
import smtplib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.message import EmailMessage

from svr_backend.core.config import get_settings

log = logging.getLogger("svr.email")


@dataclass
class SentMessage:
    to: str
    subject: str
    body: str
    at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


# In-process outbox for the "memory" backend.
OUTBOX: list[SentMessage] = []


def send_email(to: str, subject: str, body: str) -> SentMessage:
    settings = get_settings()
    msg = SentMessage(to=to, subject=subject, body=body)
    backend = settings.email_backend

    if backend == "memory":
        OUTBOX.append(msg)
        log.info("email (memory) -> %s | %s", to, subject)
        return msg

    if backend == "file":
        outdir = settings.data_dir / "outbox"
        outdir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
        (outdir / f"{stamp}.txt").write_text(
            f"To: {to}\nSubject: {subject}\n\n{body}\n", encoding="utf-8"
        )
        log.info("email (file) -> %s | %s", to, subject)
        return msg

    if backend == "smtp":
        if not settings.smtp_host:
            raise RuntimeError("SVR_SMTP_HOST is required when SVR_EMAIL_BACKEND=smtp")
        em = EmailMessage()
        em["From"] = settings.email_from
        em["To"] = to
        em["Subject"] = subject
        em.set_content(body)
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as s:
            if settings.smtp_starttls:
                s.starttls()
            if settings.smtp_user:
                s.login(settings.smtp_user, settings.smtp_password or "")
            s.send_message(em)
        log.info("email (smtp) -> %s | %s", to, subject)
        return msg

    raise RuntimeError(f"Unknown SVR_EMAIL_BACKEND: {backend}")


def echo_link_in_response() -> bool:
    """Dev backends may return the reset link in the API response (never for smtp)."""
    return get_settings().email_backend in ("memory", "file")
