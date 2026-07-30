"""Framework-level infrastructure shared across the API.

Auth-domain-agnostic on purpose: `security.py` holds the OAuth2 scheme and
the HTTP exceptions auth failures raise. Domain logic — password hashing,
JWT issuance/verification, current-user resolution — lives in
`backend/auth/` instead.

`logging.py` provides `configure_logging()`/`get_logger()`, the app's single
shared logging configuration. `rate_limit.py` provides `limiter`/
`configure_rate_limiting()`, the app's single shared API rate limiting.
"""
