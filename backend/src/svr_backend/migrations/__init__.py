"""Numbered SQL migrations applied in filename order by :mod:`svr_backend.migrations.runner`.

Plain ``.sql`` files keep the dependency surface minimal (SDD "don't over-engineer").
Each file is applied once inside a transaction and recorded in ``schema_migrations``.
"""
