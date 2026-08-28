"""Console entrypoints (see [project.scripts] in pyproject.toml).

* ``svr-backend``   - run the loopback API (Backend Service).
* ``svr-scheduler`` - run the carry-forward + backup scheduler (Scheduler Service).
* ``svr-migrate``   - apply pending SQL migrations; ``--seed-demo`` adds one user per role.
"""

from __future__ import annotations

import argparse
import sys
import time

from svr_backend.core.config import get_settings


def run_migrate(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="svr-migrate", description="Apply SQL migrations.")
    parser.add_argument("--db", help="SQLite path (default: from SVR_DB_PATH / config)")
    parser.add_argument(
        "--seed-demo",
        action="store_true",
        help="Create demo users (sales/manager/owner, password 'demo1234') if absent.",
    )
    args = parser.parse_args(argv)

    from svr_backend.core.db import connect
    from svr_backend.migrations.runner import migrate

    db_path = args.db or str(get_settings().resolved_db_path())
    conn = connect(db_path)
    try:
        applied = migrate(conn)
        print(f"Applied {len(applied)} migration(s): {applied or '(up to date)'}")
        if args.seed_demo:
            _seed_demo_users(conn)
    finally:
        conn.close()
    return 0


def _seed_demo_users(conn) -> None:
    from svr_backend.core.security import hash_password

    demo = [
        ("gsales", "G Sales", "Sales"),
        ("mmanager", "M Manager", "Manager"),
        ("oowner", "O Owner", "Owner"),
    ]
    pw = hash_password("demo1234")
    for login_name, full_name, role in demo:
        exists = conn.execute(
            "SELECT 1 FROM users WHERE login_name = ?", (login_name,)
        ).fetchone()
        if exists:
            continue
        conn.execute(
            """
            INSERT INTO users (login_name, full_name, email, role, password_hash, last_updated_by)
            VALUES (?, ?, ?, ?, ?, 'seed')
            """,
            (login_name, full_name, f"{login_name}@example.test", role, pw),
        )
        print(f"seeded user {login_name} ({role})")


def run_backend(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="svr-backend", description="Run the loopback API.")
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args(argv)

    import uvicorn

    settings = get_settings()
    try:
        from svr_backend.logging_setup import configure

        configure("backend")
    except Exception:  # logging is best-effort; never block startup
        pass

    uvicorn.run(
        "svr_backend.app:app",
        host=args.host or settings.api_host,
        port=args.port or settings.api_port,
        log_level="info",
    )
    return 0


def run_scheduler(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(prog="svr-scheduler", description="Run the scheduler.").parse_args(argv)

    from svr_backend.scheduler import build_scheduler, startup_catch_up

    try:
        from svr_backend.logging_setup import configure

        configure("scheduler")
    except Exception:
        pass

    startup_catch_up()  # catch-up-on-startup for a missed 23:59 rollover (SDD 7.7)
    sched = build_scheduler()
    sched.start()
    print("svr-scheduler running; Ctrl+C to stop.")
    try:
        while True:
            time.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        sched.shutdown()
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(run_backend())
