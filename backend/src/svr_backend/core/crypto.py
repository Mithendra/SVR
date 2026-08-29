"""Reversible field-level encryption for data that must be protected at rest
(SDD 13.3): employee bank account number, IFSC code, bank branch.

Uses Fernet (AES-128-CBC + HMAC). The key comes from ``SVR_FIELD_KEY``; if it is
unset a fixed **insecure development key** is used and a warning is logged once, so
local dev works but production is forced to supply a real key.
"""

from __future__ import annotations

import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken

from svr_backend.core.config import get_settings

log = logging.getLogger("svr.crypto")

# Deterministic dev key - NOT for production. Derived so it is a valid Fernet key.
_DEV_KEY = base64.urlsafe_b64encode(hashlib.sha256(b"svr-iocl-dev-field-key").digest())
_warned = False


def _fernet() -> Fernet:
    global _warned
    key = get_settings().field_key
    if not key:
        if not _warned:
            log.warning(
                "SVR_FIELD_KEY not set - using the insecure development key for "
                "field encryption. Set SVR_FIELD_KEY before production use (SDD 13.3)."
            )
            _warned = True
        key = _DEV_KEY.decode()
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt(plain: str | None) -> str | None:
    if plain is None or plain == "":
        return None
    return _fernet().encrypt(plain.encode()).decode()


def decrypt(token: str | None) -> str | None:
    if not token:
        return None
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken:
        return None


def mask(plain: str | None, keep: int = 4) -> str | None:
    """Return e.g. ``****1234`` for display in list views."""
    if not plain:
        return None
    tail = plain[-keep:]
    return ("*" * max(len(plain) - keep, 2)) + tail


def generate_key() -> str:
    """Helper for ops: a fresh Fernet key to put in SVR_FIELD_KEY."""
    return Fernet.generate_key().decode()
