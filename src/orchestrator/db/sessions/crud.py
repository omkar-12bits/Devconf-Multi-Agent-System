from orchestrator.db.base import DatabaseSession
from orchestrator.db.sessions.models import Session
from typing import List


def get_sessions_by_user_id(user_id: str, limit: int = 10) -> List[Session]:
    """
    Get sessions for a user, ordered by most recent first.
    
    Args:
        user_id: User ID
        limit: Maximum number of sessions to return
        
    Returns:
        List of Session instances ordered by update_time descending
    """
    with DatabaseSession() as db_session:
        return db_session.query(Session).filter(
            Session.user_id == user_id
        ).order_by(Session.update_time.desc()).limit(limit).all()


def get_session_by_id(session_id: str, user_id: str) -> Session | None:
    """
    Get a specific session by ID for a user.
    
    Args:
        session_id: Session ID
        user_id: User ID (for access control)
        
    Returns:
        Session instance or None if not found
    """
    with DatabaseSession() as db_session:
        return db_session.query(Session).filter(
            Session.id == session_id,
            Session.user_id == user_id
        ).first()
