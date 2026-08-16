from pydantic import BaseModel, Field

class MessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000, description="Patient's clinical question")
