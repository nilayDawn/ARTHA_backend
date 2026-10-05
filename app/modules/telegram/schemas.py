from pydantic import BaseModel, Field


class TelegramLinkCodeResponse(BaseModel):
    code: str = Field(..., description="Link code in FP-XXXX format")
    expires_in_seconds: int = Field(..., description="Time before link code expires")


class TelegramWebhookResponse(BaseModel):
    status: str = Field(default="ok")
