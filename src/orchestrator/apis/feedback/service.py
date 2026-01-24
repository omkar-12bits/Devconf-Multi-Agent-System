import logging
import uuid
from datetime import datetime

from orchestrator.config import app_cfg
from orchestrator.apis.feedback.models import (
    FeedbackResponse,
    FeedbackType
)
from orchestrator.db.feedback.crud import upsert_feedback
from orchestrator.db.events.crud import get_events_by_invocation
from orchestrator.utils.app_utils import extract_sub_agent_name_from_events

logger = logging.getLogger(__name__)


class FeedbackService:
    """Service for managing user feedback on agent responses."""
    
    def __init__(self):
        """Initialize feedback service."""
        logger.info("FeedbackService initialized")
    
    async def create_feedback(
        self,
        session_id: str,
        invocation_id: str,
        user_id: str,
        feedback_type: FeedbackType,
        comment: str | None = None,
        predefined_response: str | None = None
    ) -> FeedbackResponse:
        """Store feedback in database."""
        events = get_events_by_invocation(session_id, invocation_id)
        
        if not events:
            logger.warning(
                f"Cannot submit feedback: No events found for session {session_id}, "
                f"invocation {invocation_id}"
            )
            raise ValueError(
                f"Message not found. Conversation {session_id} or message {invocation_id} does not exist."
            )
        
        source_agent = extract_sub_agent_name_from_events(events) or "unknown"
        try:
            feedback = upsert_feedback(
                user_id=user_id,
                session_id=session_id,
                invocation_id=invocation_id,
                feedback_type=feedback_type.value,
                comment=comment,
                predefined_response=predefined_response,
                source_agent=source_agent,
                feedback_id=str(uuid.uuid4())
            )
            
            logger.info(
                f"Feedback {feedback.id} stored/updated: {feedback_type.value} for invocation {invocation_id}, "
                f"source_agent={source_agent}, user={user_id}"
            )
            
            return FeedbackResponse(
                feedback_id=feedback.id,
                conversation_id=feedback.session_id,
                message_id=feedback.invocation_id,
                feedback_type=FeedbackType(feedback.feedback_type),
                comment=feedback.comment,
                predefined_response=feedback.predefined_response,
                source_agent=feedback.source_agent,
                user_id=feedback.user_id,
                created_at=feedback.created_at,
                updated_at=feedback.updated_at
            )
            
        except Exception as e:
            logger.error(f"Error storing/updating feedback: {e}", exc_info=True)
            raise


# Singleton instance
_feedback_service_instance = None


def get_feedback_service() -> FeedbackService:
    """Get or create feedback service singleton instance."""
    global _feedback_service_instance
    
    if _feedback_service_instance is None:
        if not (app_cfg.DATABASE_URL and app_cfg.USE_DATABASE_SESSIONS):
            raise ValueError(
                "Database not configured or disabled. "
                "Please enable database (USE_DATABASE_SESSIONS=True and DATABASE_URL set) to use feedback feature."
            )
        _feedback_service_instance = FeedbackService()
    
    return _feedback_service_instance
