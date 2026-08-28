"""Password hashing. Argon2id via argon2-cffi.

A password is never stored, logged, returned, or transmitted in plaintext anywhere
in the system (SDD 13.1) - only this hash is persisted.
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_hasher = PasswordHasher()


def hash_password(plain: str) -> str:
    return _hasher.hash(plain)


def verify_password(plain: str, hashed: str | None) -> bool:
    if not hashed:
        return False
    try:
        return _hasher.verify(hashed, plain)
    except VerifyMismatchError:
        return False
    except Exception:
        return False
