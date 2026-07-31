# backend/auth/

Centralized authentication and authorization for the platform (JWT/OAuth2).
All authN/authZ logic lives here, including the `Depends`-compatible
dependencies (`dependencies.py`) that routes use to require a current user —
`backend/api/routes/` and `auth/router.py` consume those directly rather
than through `backend/api/dependencies/`.

- `hashing.py` — password hashing/verification (passlib/bcrypt).
- `jwt.py` — access-token issuance and verification (python-jose).
- `dependencies.py` — `get_current_user`, `get_current_active_user`,
  `require_role(*roles)`; look up the user via `backend/database/session.py`
  directly until a repository/service layer exists.
- `router.py` — `POST /auth/login` (OAuth2 password grant) and `GET /auth/me`.
- `rate_limit_key.py` — `resolve_rate_limit_key`, registered with
  `backend.core.rate_limit` at startup (`register_key_resolver`) so rate
  limiting can key by authenticated user rather than just IP, without
  `backend/core/` importing this package's JWT logic directly.

See also `backend/core/security.py` for the shared `OAuth2PasswordBearer`
scheme and the `401`/`403` exceptions this package raises.

## TODO

- [x] Password hashing utilities (passlib/bcrypt)
- [x] JWT issuance and validation (access tokens)
- [x] OAuth2 password flow (`/auth/login`)
- [x] Role-based authorization checks (`require_role`)
- [ ] Refresh tokens
- [ ] Token revocation strategy (e.g., Redis-backed denylist)
- [ ] Move user lookup behind a repository/service once that layer lands
