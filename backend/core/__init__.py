"""Framework-level infrastructure shared across the API.

Auth-domain-agnostic on purpose: `security.py` holds the OAuth2 scheme and
the HTTP exceptions auth failures raise. Domain logic — password hashing,
JWT issuance/verification, current-user resolution — lives in
`backend/auth/` instead.
"""
