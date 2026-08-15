
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str = Field(..., description="'user' or 'assistant'")
    content: str = Field(..., description="Message text content")

class ChatRequest(BaseModel):
    message: str = Field(..., description="The user's input query or message")
    history: list[ChatMessage] | None = Field(default=[], description="Previous conversation history")
    custom_api_key: str | None = Field(default=None, description="Optional custom Google Gemini API Key provided by user")

class ChatResponse(BaseModel):
    response: str = Field(..., description="The AI agent's synthesized response")
    memories_used: list[str] = Field(default=[], description="Contextual preferences retrieved from Qdrant")

class ApiKeyValidationRequest(BaseModel):
    api_key: str = Field(..., description="The Gemini API key to validate")

class ApiKeyValidationResponse(BaseModel):
    valid: bool = Field(..., description="Whether the provided API key is valid")
    message: str = Field(..., description="Status message or error detail")