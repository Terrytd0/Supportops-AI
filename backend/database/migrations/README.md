# backend/database/migrations/

Alembic migration environment.

## TODO

- [ ] Run `alembic init backend/database/migrations` (or manually create
      `env.py`, `script.py.mako`, and `versions/`) and point it at the
      SQLAlchemy models in `backend/database/models/`.
- [ ] Configure `alembic.ini` to read the database URL from
      `backend/config/settings.py` rather than a hardcoded value.
- [ ] Generate the initial migration once domain models exist.
