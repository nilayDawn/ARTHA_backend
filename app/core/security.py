from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.database import supabase, supabase_admin

security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Security(security)) -> dict:
    """
    Validates Supabase JWT access token passed in Authorization Bearer header.
    Returns the authenticated user dict if valid. Automatically ensures user profile
    exists in public.users to satisfy foreign key constraints.
    """
    token = credentials.credentials
    try:
        # Verify JWT against Supabase Auth engine
        user_response = supabase.auth.get_user(token)
        if user_response and user_response.user:
            user = user_response.user
            user_id = user.id
            email = user.email or ""
            user_metadata = user.user_metadata or {}

            # Auto-sync user into public.users if missing to prevent foreign key constraint violations
            try:
                u_check = supabase_admin.table("users").select("id").eq("id", user_id).execute()
                if not u_check.data:
                    full_name = user_metadata.get("full_name") or user_metadata.get("name") or (email.split("@")[0] if email else "User")
                    supabase_admin.table("users").insert({
                        "id": user_id,
                        "email": email,
                        "full_name": full_name
                    }).execute()
            except Exception as sync_err:
                print(f"[User Sync Notice]: {sync_err}")

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