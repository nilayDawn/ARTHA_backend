from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_auth_service
from app.core.database import supabase
from app.core.rate_limiter import RateLimiter
from app.core.security import get_current_user
from app.modules.auth.schemas import (
    AuthTokenResponse,
    PasswordResetConfirm,
    PasswordResetRequest,
    UserProfileResponse,
    UserSignIn,
    UserSignUp,
)
from app.modules.auth.service import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/signup",
    response_model=AuthTokenResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RateLimiter(max_requests=10, window_seconds=60, by_ip=True))],
)
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
            email=response.user.email,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/login",
    response_model=AuthTokenResponse,
    dependencies=[Depends(RateLimiter(max_requests=15, window_seconds=60, by_ip=True))],
)
def sign_in(credentials: UserSignIn):
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
            email=response.user.email,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {e!s}"
        )


@router.get("/me", response_model=UserProfileResponse)
def get_user_profile(
    current_user: dict = Depends(get_current_user),
    auth_service: AuthService = Depends(get_auth_service),
):
    profile = auth_service.get_user_profile(current_user["id"])
    if not profile:
        raise HTTPException(status_code=404, detail="User profile not found")
    return profile


@router.post("/logout")
def sign_out(current_user: dict = Depends(get_current_user)):
    try:
        supabase.auth.sign_out()
        return {"status": "success", "message": "Successfully logged out"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/forgot-password",
    dependencies=[Depends(RateLimiter(max_requests=5, window_seconds=60, by_ip=True))],
)
def forgot_password(payload: PasswordResetRequest):
    """Initiates a password reset email via Supabase Auth."""
    try:
        supabase.auth.reset_password_for_email(payload.email)
        return {
            "status": "success",
            "message": f"If an account with {payload.email} exists, password reset instructions have been sent.",
        }
    except Exception as e:
        # Don't leak user existence for security
        return {
            "status": "success",
            "message": f"If an account with {payload.email} exists, password reset instructions have been sent.",
        }


@router.post(
    "/reset-password",
    dependencies=[Depends(RateLimiter(max_requests=5, window_seconds=60, by_ip=True))],
)
def reset_password(
    payload: PasswordResetConfirm,
    current_user: dict = Depends(get_current_user),
):
    """Updates password for authenticated reset session."""
    try:
        supabase.auth.update_user({"password": payload.new_password})
        return {"status": "success", "message": "Password updated successfully."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
