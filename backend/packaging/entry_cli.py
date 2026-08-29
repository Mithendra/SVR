"""Frozen-backend entrypoint: ``svr-backend <subcommand> [args...]``.

PyInstaller bundles this into ``svr-backend.exe`` (see ``svr_backend.spec``). Each
subcommand maps 1:1 onto a console-script function in :mod:`svr_backend.cli`, so the
frozen build and a dev ``pip install -e .`` behave identically:

    svr-backend migrate [--db PATH] [--seed-demo]   -> svr_backend.cli:run_migrate
    svr-backend serve   [--host H] [--port N]        -> svr_backend.cli:run_backend
    svr-backend scheduler                            -> svr_backend.cli:run_scheduler
    svr-backend gen-key                              -> a fresh Fernet key for SVR_FIELD_KEY

The two Windows Services are separate exes (``svr-backend-service.exe`` /
``svr-scheduler-service.exe``) built from the same spec.
"""

from __future__ import annotations

import sys

_USAGE = "usage: svr-backend {migrate|serve|scheduler|gen-key} [args...]"


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print(_USAGE, file=sys.stderr)
        return 2
    if args[0] in ("-h", "--help"):
        print(_USAGE)
        return 0

    cmd, rest = args[0], args[1:]

    if cmd == "migrate":
        from svr_backend.cli import run_migrate

        return run_migrate(rest)
    if cmd == "serve":
        from svr_backend.cli import run_backend

        return run_backend(rest)
    if cmd == "scheduler":
        from svr_backend.cli import run_scheduler

        return run_scheduler(rest)
    if cmd == "gen-key":
        from svr_backend.core.crypto import generate_key

        print(generate_key())
        return 0

    print(f"svr-backend: unknown subcommand {cmd!r}\n{_USAGE}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
