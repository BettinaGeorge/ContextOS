import logging
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from src.core.config import get_settings

logger = logging.getLogger("contextos.auth")

_bearer_scheme = HTTPBearer(auto_error=False)


class CurrentUser:
    """The authenticated user's identity, extracted from a verified Supabase JWT."""

    def __init__(self, user_id: str):
        self.user_id = user_id


@lru_cache
def _jwks_client() -> PyJWKClient:
    """Supabase's newer projects sign session tokens asymmetrically (ES256,
    via "JWT Signing Keys") rather than the legacy HS256 shared secret —
    found by actually testing a real sign-in, not assumed. The JWKS endpoint
    is public (no secret involved); PyJWKClient fetches and caches the
    matching public key by the token's `kid` header."""
    settings = get_settings()
    jwks_url = f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"
    return PyJWKClient(jwks_url, cache_keys=True)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> CurrentUser:
    """Verifies the Supabase Auth JWT sent as a Bearer token (research.md §2,
    revised after real sign-in testing surfaced the ES256/JWKS requirement).

    Supabase issues the token on sign-in; we only ever verify it here — no
    separate backend session store. The `sub` claim is the Supabase user id
    and becomes the `owner_user_id` used to scope every workspace query.
    """
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    settings = get_settings()
    try:
        header = jwt.get_unverified_header(credentials.credentials)
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed token"
        ) from exc

    try:
        if header.get("alg") == "HS256":
            # Older Supabase projects (or ones still on the legacy secret)
            # sign this way — kept as a fallback, not assumed as the default.
            payload = jwt.decode(
                credentials.credentials,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
            )
        else:
            signing_key = _jwks_client().get_signing_key_from_jwt(credentials.credentials)
            payload = jwt.decode(
                credentials.credentials,
                signing_key.key,
                algorithms=[header.get("alg", "ES256")],
                audience="authenticated",
            )
    except jwt.PyJWTError as exc:
        logger.warning("JWT verification failed: %s | header=%s", exc, header)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        ) from exc

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing subject claim"
        )
    return CurrentUser(user_id=user_id)
