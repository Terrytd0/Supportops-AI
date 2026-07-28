# backend/core/

Framework-level infrastructure that other parts of `backend/` may depend on,
but that isn't itself business or auth-domain logic.

- `security.py` — the shared `OAuth2PasswordBearer` scheme and the `401`/`403`
  `HTTPException`s auth failures raise. Kept separate from `backend/auth/` so
  any future router can depend on the scheme/exceptions without importing
  the auth package's JWT/hashing internals.

## TODO

- [ ] Revisit once `backend/api/middleware/` exists — request-ID/correlation
      helpers and other cross-cutting concerns likely belong here too.
