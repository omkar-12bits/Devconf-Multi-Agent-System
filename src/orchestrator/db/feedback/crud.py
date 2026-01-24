from orchestrator.db.base import DatabaseSession
from orchestrator.db.feedback.models import Feedback


def upsert_feedback(
    user_id: str,
    session_id: str,
    invocation_id: str,
    feedback_type: str,
    comment: str | None = None,
    predefined_response: str | None = None,
    source_agent: str | None = None,
    feedback_id: str | None = None
) -> Feedback:
    """Create or update feedback (upsert)."""
    with DatabaseSession() as db_session:
        existing = db_session.query(Feedback).filter(
            Feedback.user_id == user_id,
            Feedback.invocation_id == invocation_id
        ).first()
        
        if existing:
            existing.feedback_type = feedback_type
            existing.comment = comment
            existing.predefined_response = predefined_response
            existing.source_agent = source_agent
            
            db_session.commit()
            db_session.refresh(existing)
            return existing
        else:
            new_feedback = Feedback(
                id=feedback_id or str(__import__('uuid').uuid4()),
                session_id=session_id,
                invocation_id=invocation_id,
                user_id=user_id,
                feedback_type=feedback_type,
                comment=comment,
                predefined_response=predefined_response,
                source_agent=source_agent
            )
            
            db_session.add(new_feedback)
            db_session.commit()
            db_session.refresh(new_feedback)
            return new_feedback
