"""Calculation engine - the single source of truth for every formula (SDD 7.3).

The frontend keeps a JS mirror of this logic for responsive typing, but the backend
recomputes on every save and its result wins. Every entry path (manual, OCR, Excel
import) converges here.
"""
