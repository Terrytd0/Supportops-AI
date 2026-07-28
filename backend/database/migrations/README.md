# backend/database/migrations/

This folder is a stub left over from initial scaffolding and is **not**
where Alembic actually lives. The migration environment was initialized at
the repository root instead: `alembic.ini` and `alembic/`
(`alembic/env.py`, `alembic/script.py.mako`, `alembic/versions/`), driven by
`backend.config.settings.get_settings().database_url` and targeting
`backend.database.base.Base.metadata` (which imports every model in
`backend/database/models/`).

Run migrations from the repository root:

```bash
alembic upgrade head
```

## TODO

- [ ] Decide whether to move `alembic/` under this package for consistency
      with the rest of `backend/database/`, or leave it at the repo root
      (common Alembic convention) and remove this stub folder instead.
