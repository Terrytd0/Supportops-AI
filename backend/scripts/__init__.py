"""One-off / operational scripts run via `python -m backend.scripts.<name>`.

Not part of the FastAPI app import graph — nothing under `backend/` should
import from here. Scripts in this package reuse the same session factory,
models, and utilities the app itself uses; they never reimplement them.
"""
