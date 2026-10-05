from pydantic import BaseModel, EmailStr, Field


class ReportRequest(BaseModel):
    user_email: EmailStr | None = None
    month: str | None = Field(None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$")


class ReportResponse(BaseModel):
    status: str = "success"
    message: str
