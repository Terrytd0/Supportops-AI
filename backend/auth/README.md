# backend/auth/

Centralized authentication and authorization for the platform (JWT/OAuth2).
All authN/authZ logic must live here; `backend/api/` consumes it exclusively
through dependencies in `backend/api/dependencies/`.

## TODO

- [ ] JWT issuance and validation (access + refresh tokens)
- [ ] OAuth2 password/authorization-code flow (per `backend/config` settings)
- [ ] Password hashing utilities (passlib/bcrypt)
- [ ] Role-based / permission-based authorization checks
- [ ] Token revocation strategy (e.g., Redis-backed denylist)
