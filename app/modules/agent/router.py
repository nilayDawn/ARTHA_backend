from fastapi import APIRouter, Depends, HTTPException, status

from app.adapters.llm.gemini_adapter import custom_api_key_ctx
from app.api.dependencies import get_ai_agent_service, get_llm_adapter
from app.core.rate_limiter import RateLimiter
from app.core.security import get_current_user
from app.modules.agent.schemas import (
    ApiKeyValidationRequest,
    ApiKeyValidationResponse,
    ChatRequest,
    ChatResponse,
)
from app.modules.agent.service import AIAgentService
from app.ports.llm import LLMProviderPort

router = APIRouter(prefix="/chat", tags=["Chat & AI"])


@router.post(
    "/validate-key",
    response_model=ApiKeyValidationResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RateLimiter(max_requests=10, window_seconds=60))],
)
def validate_user_api_key(
    payload: ApiKeyValidationRequest,
    current_user: dict = Depends(get_current_user),
    llm: LLMProviderPort = Depends(get_llm_adapter),
):
    valid, message = llm.validate_key(payload.api_key)
    return ApiKeyValidationResponse(valid=valid, message=message)


@router.post(
    "",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(RateLimiter(max_requests=20, window_seconds=60))],
)
def chat_with_agent(
    payload: ChatRequest,
    current_user: dict = Depends(get_current_user),
    agent_service: AIAgentService = Depends(get_ai_agent_service),
):
    user_id = current_user["id"]
    token = None

    if payload.custom_api_key and payload.custom_api_key.strip():
        token = custom_api_key_ctx.set(payload.custom_api_key.strip())

    try:
        history = [msg.model_dump() for msg in (payload.history or [])]
        res = agent_service.process_chat(
            user_id=user_id,
            message=payload.message,
            history=history,
            custom_api_key=payload.custom_api_key,
        )
        return ChatResponse(
            response=res["response"],
            memories_used=res.get("memories_used", []),
        )
    except Exception as e:
        err_str = str(e)
        if any(kw in err_str.lower() for kw in ["quota", "exhausted", "429", "rate limit", "resource_exhausted", "api_key"]):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="API_KEY_QUOTA_EXHAUSTED: System default API key quota has been exhausted. Please configure your own ARTHA API Key in settings to continue using AI CFO features."
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while processing your AI query: {err_str}"
        )
    finally:
        if token:
            custom_api_key_ctx.reset(token)
