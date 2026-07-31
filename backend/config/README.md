# backend/config/

Application configuration, sourced from environment variables.

- `settings.py` — `Settings` (pydantic-settings) and `get_settings()` accessor.

## Conventions

- All configuration must be read through `Settings`, never via `os.environ`
  directly elsewhere in the codebase.
- No secrets should be committed; local defaults in `settings.py` are for
  scaffolding only and must be overridden via `.env` / real secrets management
  before any shared or production deployment.

## TODO

- [ ] Add per-environment settings classes or profiles (local/dev/staging/prod)
- [ ] Add agent/graph tuning parameters (max turns, retry policy)
- [ ] Wire secrets management (e.g., cloud secrets manager) for non-local environments
