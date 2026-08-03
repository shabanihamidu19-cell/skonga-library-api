"""
SKONGA Library API — Security
==============================
Service-to-service authentication using a bearer token.

Design decisions:
- The token itself is never stored anywhere on this service — only its
  SHA-256 hash is kept (in the SERVICE_TOKEN_HASH env var).
- We compare hashes using hmac.compare_digest() instead of == to prevent
  timing-based attacks (an attacker cannot learn how many characters of
  the token they got right by measuring response time).
- CORS is intentionally NOT configured anywhere — the client (APK/browser)
  must never reach this API directly. Absence of CORS headers means any
  browser preflight request will be refused automatically.
"""
import hashlib
import hmac

from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

# Fail fast if SERVICE_TOKEN_HASH is not configured — avoids obscure errors later
if not getattr(settings, "SERVICE_TOKEN_HASH", None):
    raise RuntimeError(
        "SERVICE_TOKEN_HASH is not configured. Set SERVICE_TOKEN_HASH env var to the SHA-256 hex of the service token."
    )

_bearer_scheme = HTTPBearer(auto_error=False)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def verify_service_token(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer_scheme),
) -> str:
    """
    FastAPI dependency — add to any endpoint that must be protected.

    Usage:
        @router.get("/subjects")
        def list_subjects(token: str = Depends(verify_service_token)):
            ...

    Returns the token string if valid (rarely needed); raises HTTPException
    with 401 or 403 if missing or wrong.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header is required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    incoming_hash = _hash_token(credentials.credentials)

    if not hmac.compare_digest(incoming_hash, settings.SERVICE_TOKEN_HASH):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid service token",
        )

    return credentials.credentials
