# backend/database/

Persistence layer.

- `models/` — SQLAlchemy declarative models (ORM layer only, no business logic).
- `migrations/` — Alembic migration environment and version scripts.
- `repositories/` — Repository pattern: all query logic lives here; services
  depend on repositories, never on raw SQLAlchemy sessions directly.

## TODO

- [x] Add async engine/session factory and declarative base (`base.py`, `session.py`)
- [x] Define domain models per `docs/database_schema.md` (`models/`)
- [ ] Initialize Alembic (`alembic init`) targeting `migrations/`
- [ ] Define repository interfaces per model/aggregate
- [ ] Add a FastAPI dependency yielding a request-scoped `AsyncSession`
