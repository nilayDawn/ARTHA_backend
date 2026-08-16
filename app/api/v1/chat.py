from fastapi import APIRouter, Depends, HTTPException, status
from langchain_core.messages import AIMessage, HumanMessage

from app.agent.graph import financial_agent
from app.core.llm_setup import custom_api_key_ctx, validate_gemini_api_key
from app.core.security import get_current_user
from app.schemas.chat import (
    ApiKeyValidationRequest,
    ApiKeyValidationResponse,
    ChatRequest,
    ChatResponse,
)

router = APIRouter(prefix="/chat", tags=["Chat & AI"])


@router.post("/validate-key", response_model=ApiKeyValidationResponse, status_code=status.HTTP_200_OK)
def validate_user_api_key(
    payload: ApiKeyValidationRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Validates a custom user-supplied Gemini API key.
    """
    valid, message = validate_gemini_api_key(payload.api_key)
    return ApiKeyValidationResponse(valid=valid, message=message)


@router.post("", response_model=ChatResponse, status_code=status.HTTP_200_OK)
def chat_with_agent(
    payload: ChatRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Main conversational AI endpoint. Runs the user request through the 
    LangGraph agent (DB query -> Qdrant Memory recall -> Gemini Flash reasoning).
    Supports custom user-provided API key via payload or HTTP header.
    """
    user_id = current_user["id"]
    token = None

    if payload.custom_api_key and payload.custom_api_key.strip():
        token = custom_api_key_ctx.set(payload.custom_api_key.strip())

    try:
        # Reconstruct message history for LangGraph
        messages = []
        for msg in payload.history:
            if msg.role == "user":
                messages.append(HumanMessage(content=msg.content))
            elif msg.role == "assistant":
                messages.append(AIMessage(content=msg.content))

        # Append current incoming query
        messages.append(HumanMessage(content=payload.message))

        # Invoke LangGraph agent graph
        initial_state = {
            "messages": messages,
            "user_id": user_id,
            "memories": [],
            "db_context": {}
        }
        
        final_state = financial_agent.invoke(initial_state)
        
        # Retrieve final response message
        last_message = final_state["messages"][-1]
        response_text = last_message.content if isinstance(last_message, AIMessage) else str(last_message)

        return ChatResponse(
            response=response_text,
            memories_used=final_state.get("memories", [])
        )

    except Exception as e:
        err_str = str(e)
        print(f"[Chat Endpoint Error]: {err_str}")
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