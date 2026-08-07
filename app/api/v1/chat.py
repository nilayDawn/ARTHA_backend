from fastapi import APIRouter, Depends, HTTPException, status
from langchain_core.messages import HumanMessage, AIMessage
from app.schemas.chat import ChatRequest, ChatResponse
from app.core.security import get_current_user
from app.agent.graph import financial_agent

router = APIRouter(prefix="/chat", tags=["Chat & AI"])

@router.post("", response_model=ChatResponse, status_code=status.HTTP_200_OK)
def chat_with_agent(
    payload: ChatRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Main conversational AI endpoint. Runs the user request through the 
    LangGraph agent (DB query -> Qdrant Memory recall -> Gemini 2.5 Flash reasoning).
    """
    user_id = current_user["id"]

    # Reconstruct message history for LangGraph
    messages = []
    for msg in payload.history:
        if msg.role == "user":
            messages.append(HumanMessage(content=msg.content))
        elif msg.role == "assistant":
            messages.append(AIMessage(content=msg.content))

    # Append current incoming query
    messages.append(HumanMessage(content=payload.message))

    try:
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
        print(f"[Chat Endpoint Error]: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while processing your AI query: {str(e)}"
        )