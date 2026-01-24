from pydantic import BaseModel, Field, field_validator
from datetime import datetime


class StreamEventData(BaseModel):
    """Streaming event data model for SSE responses."""
    
    author: str = Field(description="Agent/user that generated this event")
    is_final: bool = Field(description="Whether this is the final event from this agent")
    conversation_id: str = Field(description="Conversation ID")
    message_id: str = Field(description="Message ID")
    event_type: str = Field(description="Event type: progress, content, done, or error")
    progress_message: str | None = Field(default=None, description="Progress message for progress events")
    content: str | None = Field(default=None, description="Response content for content events")
    thinking: str | None = Field(default=None, description="Thinking/reasoning if available")
    error: str | None = Field(default=None, description="Error message if error occurred")


class NewConversationResponse(BaseModel):
    """Response model for new conversation creation."""
    conversation_id: str = Field(
        description="UUID of the created conversation",
        examples=["550e8400-e29b-41d4-a716-446655440000"]
    )
    user_id: str = Field(
        description="User ID",
        examples=["anonymous", "user-123"]
    )
    app_name: str = Field(
        description="Application name",
        examples=["devconf_multi_agent"]
    )


class MessageRequest(BaseModel):
    """API Request model represents a message sent from user."""

    input: str = Field(
        description="The user's question or input for this message",
        examples=[
            "What is Red Hat OpenShift?",
            "How do I configure RHEL firewall?",
            "What are best practices for container security?",
        ],
    )

    @field_validator("input")
    @classmethod
    def trim_whitespace(cls, value: str) -> str:
        trimmed_input = value.strip()
        if not trimmed_input:
            raise ValueError("Input cannot be empty.")
        return trimmed_input

    stream: bool = Field(
        default=True,
        description="Whether or not to stream back response"
    )


class MessageChunkResponse(BaseModel):
    """Response model for message chunks (streaming or complete)."""
    content: str | None = Field(
        default=None,
        description="Message content"
    )
    conversation_id: str = Field(description="Conversation ID")
    message_id: str | None = Field(default=None, description="Message ID")
    user_id: str = Field(description="User ID")
    thinking: str = Field(default="", description="Thinking/reasoning if available")
    done: bool = Field(default=False, description="Whether this is the final chunk")