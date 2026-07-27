# backend/database/

Persistence layer.

- `models/` — SQLAlchemy declarative models (ORM layer only, no business logic).
- `migrations/` — Alembic migration environment and version scripts.
- `repositories/` — Repository pattern: all query logic lives here; services
  depend on repositories, never on raw SQLAlchemy sessions directly.

## TODO

- [ ] Add async engine/session factory and declarative base (likely `database/session.py`)
- [ ] Initialize Alembic (`alembic init`) targeting `migrations/`
- [ ] Define initial domain models (e.g. Ticket, Conversation, Message, User)
- [ ] Define repository interfaces per model/aggregate
