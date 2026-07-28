"""FastAPI dependency providers (db sessions, common query params, etc).

Auth dependencies (`get_current_user`, `get_current_active_user`,
`require_role`) live in `backend/auth/dependencies.py` instead — see
backend/auth/README.md.

TODO: add get_db_session and pagination dependencies.
"""
