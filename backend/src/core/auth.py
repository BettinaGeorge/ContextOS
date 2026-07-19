import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from src.core.config import get_settings

_bearer_scheme = HTTPBearer(auto_error=False)


class CurrentUser:
    """The authenticated user's identity, extracted from a verified Supabase JWT."""

    def __init__(self, user_id: str):
        self.user_id = user_id


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> CurrentUser:
    """Verifies the Supabase Auth JWT sent as a Bearer token (research.md §2).

    Supabase issues the token on sign-in; we only ever verify it here — no
    separate backend session store. The `sub` claim is the Supabase user id
    and becomes the `owner_user_id` used to scope every workspace query.
    """
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    settings = get_settings()
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token"
        ) from exc

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token missing subject claim"
        )
    return CurrentUser(user_id=user_id)
