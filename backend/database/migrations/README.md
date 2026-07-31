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

Check for model changes that don't have a migration yet (what `alembic
upgrade head` alone won't tell you -- it only replays *existing* migration
files, it doesn't compare them against the current models):

```bash
alembic check
```

`tests/integration/test_schema_migrations.py` runs the equivalent check
automatically against a real database. Three migrations exist so far
(`alembic/versions/`): an initial baseline (`8f0d1bb0d4bb`, reconstructed --
see its docstring for why), `knowledge_articles` + `approval_requests`'s
AI-execution-context columns (`757988297d96`), and making
`approval_requests.decided_at` timezone-aware (`26f06c6b17b3`). The middle
one is the cautionary tale: both were added to
`backend/database/models/` without ever running `alembic revision
--autogenerate`, so the live database silently fell out of sync with the
models until it started rejecting real queries at runtime ("relation ...
does not exist" / "column ... does not exist") -- **always run `alembic
revision --autogenerate` (and read the diff) after changing a model.**

## TODO

- [ ] Decide whether to move `alembic/` under this package for consistency
      with the rest of `backend/database/`, or leave it at the repo root
      (common Alembic convention) and remove this stub folder instead.
