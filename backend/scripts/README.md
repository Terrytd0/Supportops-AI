# backend/scripts/

One-off / operational scripts, run directly rather than imported by the app
(`python -m backend.scripts.<name>`). Scripts here reuse the app's existing
session factory, models, and utilities — they never reimplement database
connections, hashing, or auth logic.

- `seed.py` — seeds baseline development data (default users, demo
  customers, demo tickets). Idempotent: safe to run more than once. See its
  module docstring for details.

## TODO

- [ ] A `reset.py` / `truncate.py` counterpart for local dev resets, if needed
