from fastapi import APIRouter, Depends, HTTPException, status

from app.core.database import supabase
from app.core.security import get_current_user
from app.schemas.auth import (
    AuthTokenResponse,
    UserProfileResponse,
    UserSignIn,
    UserSignUp,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/signup", response_model=AuthTokenResponse, status_code=status.HTTP_201_CREATED)
def sign_up(user_data: UserSignUp):
    """
    Register a new user in Supabase Auth.
    The postgres trigger 'on_auth_user_created' automatically creates the user record in public.users.
    """
    try:
        response = supabase.auth.sign_up({
            "email": user_data.email,
            "password": user_data.password,
            "options": {
                "data": {
                    "full_name": user_data.full_name or ""
                }
            }
        })
        
        if not response.user or not response.session:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sign-up failed or email confirmation required."
            )
            
        return AuthTokenResponse(
            access_token=response.session.access_token,
            user_id=response.user.id,
            email=response.user.email
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/login", response_model=AuthTokenResponse)
def sign_in(credentials: UserSignIn):
    """Authenticate existing user with Email and Password."""
    try:
        response = supabase.auth.sign_in_with_password({
            "email": credentials.email,
            "password": credentials.password
        })
        
        if not response.session:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
            
        return AuthTokenResponse(
            access_token=response.session.access_token,
            user_id=response.user.id,
            email=response.user.email
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {e!s}"
        )

@router.get("/me", response_model=UserProfileResponse)
def get_user_profile(current_user: dict = Depends(get_current_user)):
    """Retrieve profile data for the authenticated user from public.users table."""
    try:
        res = supabase.table("users").select("id, email, full_name, telegram_chat_id, created_at").eq("id", current_user["id"]).execute()
        if not res.data:
            raise HTTPException(status_code=404, detail="User profile not found")
        return res.data[0]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/logout")
def sign_out(current_user: dict = Depends(get_current_user)):
    """Sign out the current user."""
    try:
        supabase.auth.sign_out()
        return {"status": "success", "message": "Successfully logged out"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))