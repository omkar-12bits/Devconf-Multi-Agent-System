from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from enum import Enum


class FeedbackType(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"


class FeedbackRequest(BaseModel):
    """Request model for submitting feedback on an AI response."""
    
    feedback_type: FeedbackType = Field(
        description="The message's rating (positive or negative)"
    )
    comment: str | None = Field(
        default=None,
        max_length=1000,
        description="Optional freeform feedback from user",
        examples=[
            "This resolved my issue in one go!",
            "The response wasn't accurate for my use case",
        ]
    )
    predefined_response: str | None = Field(
        default=None,
        max_length=500,
        description="Optional predefined feedback text submitted by user from UI"
    )
    
    @field_validator("comment")
    @classmethod
    def trim_comment_whitespace(cls, value: str | None) -> str | None:
        """Trim whitespace from comment field."""
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed if trimmed else None
    
    @field_validator("predefined_response")
    @classmethod
    def trim_predefined_response_whitespace(cls, value: str | None) -> str | None:
        """Trim whitespace from predefined_response field."""
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed if trimmed else None


class FeedbackResponse(BaseModel):
    """Response model after submitting feedback."""
    
    feedback_id: str = Field(description="Unique feedback identifier")
    conversation_id: str = Field(description="Conversation ID")
    message_id: str = Field(description="Message ID")
    feedback_type: FeedbackType = Field(description="positive or negative")
    comment: str | None = Field(default=None, description="Optional freeform comment")
    predefined_response: str | None = Field(default=None, description="Optional predefined feedback text")
    source_agent: str | None = Field(default=None, description="Sub-agent that generated the response (null if no routing)")
    user_id: str = Field(description="User who submitted feedback")
    created_at: datetime = Field(description="When feedback was first submitted")
    updated_at: datetime = Field(description="When feedback was last updated (same as created_at initially)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "feedback_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                "conversation_id": "358a9020-81df-45fa-a61e-37a911f977c8",
                "message_id": "inv-abc123",
                "feedback_type": "positive",
                "comment": "Solved my issue",
                "predefined_response": "Accurate and complete",
                "source_agent": "google_search_agent",
                "user_id": "user-123",
                "created_at": "2026-01-19T10:30:00",
                "updated_at": "2026-01-19T10:30:00"
            }
        }
