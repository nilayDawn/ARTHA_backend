from pydantic import BaseModel, Field
from typing import List, Optional

class ChatMessage(BaseModel):
    role: str = Field(..., description="'user' or 'assistant'")
    content: str = Field(..., description="Message text content")

class ChatRequest(BaseModel):
    message: str = Field(..., description="The user's input query or message")
    history: Optional[List[ChatMessage]] = Field(default=[], description="Previous conversation history")

class ChatResponse(BaseModel):
    response: str = Field(..., description="The AI agent's synthesized response")
    memories_used: List[str] = Field(default=[], description="Contextual preferences retrieved from Qdrant")