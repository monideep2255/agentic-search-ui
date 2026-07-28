"""Auth primitives for System 3.

Password hashing (`passwords.py`) and token minting/verification
(`tokens.py`). Pure functions only: no HTTP, no database access.

The auth router, request/response schemas, and FastAPI dependencies that
wire these primitives into `/auth/*` endpoints are a separate, later
ticket (T-1.1-03) and do not live in this package yet.
"""
