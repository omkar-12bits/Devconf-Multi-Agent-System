from datetime import datetime
from typing import List
from pydantic import BaseModel, Field


class ConversationTurn(BaseModel):
    """Represents a single conversation turn (question + answer)."""
    
    conversation_id: str = Field(
        description="Conversation ID",
        examples=["358a9020-81df-45fa-a61e-37a911f977c8"]
    )
    message_id: str = Field(
        description="Message ID",
        examples=["e-c0937d82-c39f-4a22-a32d-4cbc390e7f69"]
    )
    question: str = Field(
        description="User's question",
        examples=["What is OpenShift?", "How do I install RHEL?"]
    )
    answer: str = Field(
        description="Agent's response",
        examples=["OpenShift is a container orchestration platform..."]
    )
    thinking: str | None = Field(
        default=None,
        description="Agent's reasoning process (if thinking mode enabled)",
        examples=["The user is asking about OpenShift pods..."]
    )
    timestamp: datetime = Field(
        description="When the question was asked",
        examples=["2025-12-27T14:33:20"]
    )


class SessionSummary(BaseModel):
    """Summary of a conversation session (without full conversation turns)."""
    
    conversation_id: str = Field(
        description="Unique conversation identifier",
        examples=["358a9020-81df-45fa-a61e-37a911f977c8"]
    )
    user_id: str = Field(
        description="User who owns this session",
        examples=["51298982", "user-123"]
    )
    title: str = Field(
        description="Title/preview of the conversation (first question)",
        examples=["What is OpenShift?", "How do I configure RHEL?"]
    )
    created_at: datetime = Field(
        description="When session was created",
        examples=["2025-12-27T09:03:13"]
    )
    updated_at: datetime = Field(
        description="When session was last updated",
        examples=["2025-12-27T09:08:01"]
    )
    turn_count: int = Field(
        description="Number of conversation turns",
        examples=[3, 5, 10],
        ge=0
    )


class SessionDetail(BaseModel):
    """Detailed conversation session with all turns."""
    
    conversation_id: str = Field(
        description="Unique conversation identifier",
        examples=["358a9020-81df-45fa-a61e-37a911f977c8"]
    )
    user_id: str = Field(
        description="User who owns this session",
        examples=["51298982", "user-123"]
    )
    title: str = Field(
        description="Title/preview of the conversation (first question)",
        examples=["What is OpenShift?", "How do I configure RHEL?"]
    )
    created_at: datetime = Field(
        description="When session was created",
        examples=["2025-12-27T09:03:13"]
    )
    updated_at: datetime = Field(
        description="When session was last updated",
        examples=["2025-12-27T09:08:01"]
    )
    turn_count: int = Field(
        description="Number of conversation turns",
        examples=[3, 5, 10],
        ge=0
    )
    turns: List[ConversationTurn] = Field(
        default_factory=list, 
        description="Conversation turns (Q&A pairs)"
    )


class HistoryResponse(BaseModel):
    """Response containing multiple session summaries."""
    
    sessions: List[SessionSummary] = Field(
        description="List of conversation sessions (metadata only)"
    )
    total_count: int = Field(
        description="Total number of sessions returned",
        examples=[5, 10, 20],
        ge=0
    )

