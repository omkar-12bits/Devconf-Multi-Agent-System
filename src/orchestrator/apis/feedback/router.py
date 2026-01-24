import logging
from fastapi import APIRouter, HTTPException, Path, Depends
from typing import Annotated

from orchestrator.apis.feedback.models import (
    FeedbackRequest,
    FeedbackResponse
)
from orchestrator.apis.feedback.service import get_feedback_service
from orchestrator.apis.models import User
from orchestrator.apis.auth import user_authorization

logger = logging.getLogger(__name__)

feedback_router = APIRouter(prefix="/feedback", tags=["Feedback"])


@feedback_router.post(
    "/conversation/{conversation_id}/message/{message_id}",
    response_model=FeedbackResponse,
    summary="Submit or update feedback for a specific message",
    description="Submit positive or negative feedback for an AI response."
)
async def submit_feedback(
    conversation_id: Annotated[str, Path(
        description="Conversation ID",
        examples=["358a9020-81df-45fa-a61e-37a911f977c8"]
    )],
    message_id: Annotated[str, Path(
        description="Message ID",
        examples=["e-c0937d82-c39f-4a22-a32d-4cbc390e7f69"]
    )],
    feedback: FeedbackRequest,
    user: Annotated[User, Depends(user_authorization)]
):
    """Submit feedback for a specific message in a conversation."""
    try:
        logger.info(
            f"Submitting feedback for message {message_id} in conversation {conversation_id}, "
            f"user {user.id}, type={feedback.feedback_type.value}"
        )
        
        try:
            feedback_service = get_feedback_service()
        except ValueError as ve:
            logger.error(f"Feedback service not available: {ve}")
            raise HTTPException(
                status_code=500,
                detail="Feedback feature not available. Database storage is not enabled."
            )
        
        try:
            feedback_response = await feedback_service.create_feedback(
                session_id=conversation_id,
                invocation_id=message_id,
                user_id=user.id,
                feedback_type=feedback.feedback_type,
                comment=feedback.comment,
                predefined_response=feedback.predefined_response
            )
        except ValueError as ve:
            logger.warning(f"Validation error: {ve}")
            raise HTTPException(
                status_code=404,
                detail=str(ve)
            )
        
        logger.info(
            f"Feedback {feedback_response.feedback_id} created successfully: "
            f"{feedback.feedback_type.value} for message {message_id}, "
            f"source_agent={feedback_response.source_agent}"
        )
        
        return feedback_response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error submitting feedback for message {message_id} in conversation {conversation_id}: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to submit feedback: {str(e)}"
        )
