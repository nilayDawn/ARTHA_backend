from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.dependencies import get_auth_service
from app.core.database import supabase

security = HTTPBearer()


def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)) -> dict:
    token = credentials.credentials
    try:
        # Verify JWT against Supabase Auth engine
        user_response = supabase.auth.get_user(token)
        if user_response and user_response.user:
            user = user_response.user
            user_id = user.id
            email = user.email or ""
            user_metadata = user.user_metadata or {}

            # Sync user profile into public users table via cached AuthService
            auth_service = get_auth_service()
            auth_service.sync_user_if_needed(user_id=user_id, email=email, user_metadata=user_metadata)

            return {
                "id": user_id,
                "email": email,
                "user_metadata": user_metadata,
            }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {e!s}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired access token",
        headers={"WWW-Authenticate": "Bearer"},
    )