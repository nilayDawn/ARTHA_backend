from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str = Field(..., pattern=r"^(user|assistant)$", description="'user' or 'assistant'")
    content: str = Field(..., min_length=1, max_length=4000, description="Message text content up to 4000 chars")


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000, description="The user's query up to 4000 chars")
    history: list[ChatMessage] = Field(default=[], max_length=50, description="Conversation history up to 50 messages")
    custom_api_key: str | None = Field(default=None, max_length=120, description="Optional custom Google Gemini API Key")


class ChatResponse(BaseModel):
    response: str = Field(..., description="The AI agent's synthesized response")
    memories_used: list[str] = Field(default=[], description="Contextual preferences retrieved from Qdrant")


class ApiKeyValidationRequest(BaseModel):
    api_key: str = Field(..., min_length=10, max_length=120, description="The Gemini API key to validate")


class ApiKeyValidationResponse(BaseModel):
    valid: bool = Field(..., description="Whether the provided API key is valid")
    message: str = Field(..., description="Status message or error detail")
