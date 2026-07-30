# backend/scripts/

One-off / operational scripts, run directly rather than imported by the app
(`python -m backend.scripts.<name>`). Scripts here reuse the app's existing
session factory, models, and utilities — they never reimplement database
connections, hashing, or auth logic.

- `seed.py` — seeds baseline development data (default users, demo
  customers, demo tickets). Idempotent: safe to run more than once. See its
  module docstring for details.
- `load_test.py` — fires 50 concurrent requests at the running app's
  supervisor approve/reject endpoint (no `POST /tickets` endpoint exists
  yet) and reports latency/throughput; requires the app to already be
  running separately (`uvicorn backend.main:app`). Sample ticket payloads
  live in `load_test_tickets.py`. See its module docstring for details.

## TODO

- [ ] A `reset.py` / `truncate.py` counterpart for local dev resets, if needed
