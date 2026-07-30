# backend/core/

Framework-level infrastructure that other parts of `backend/` may depend on,
but that isn't itself business or auth-domain logic.

- `security.py` — the shared `OAuth2PasswordBearer` scheme and the `401`/`403`
  `HTTPException`s auth failures raise. Kept separate from `backend/auth/` so
  any future router can depend on the scheme/exceptions without importing
  the auth package's JWT/hashing internals.
- `logging.py` — `configure_logging()` installs the app's single formatted
  stdout handler (called once, from `backend/main.py`); `get_logger(__name__)`
  is how every other module gets its logger.
- `rate_limit.py` — `limiter` is the shared slowapi `Limiter` instance routes
  decorate with `@limiter.limit(...)`; `configure_rate_limiting(app)` wires
  it into the app (called once, from `backend/main.py`), including a 429
  handler that logs throttled requests via `logging.py`.

## TODO

- [ ] Revisit once `backend/api/middleware/` exists — request-ID/correlation
      helpers and other cross-cutting concerns likely belong here too.
