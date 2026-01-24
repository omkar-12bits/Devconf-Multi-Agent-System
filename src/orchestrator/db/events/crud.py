from orchestrator.db.base import DatabaseSession
from orchestrator.db.events.models import Event
from typing import List


def get_events_by_invocation(session_id: str, invocation_id: str) -> List[Event]:
    """
    Get all events for a specific invocation (message).
    
    Used for extracting source agent and analyzing message flow.
    
    Args:
        session_id: Session/conversation ID
        invocation_id: Invocation ID (message ID)
        
    Returns:
        List of Event instances ordered by timestamp
    """
    with DatabaseSession() as db_session:
        return db_session.query(Event).filter(
            Event.session_id == session_id,
            Event.invocation_id == invocation_id
        ).order_by(Event.timestamp).all()


def get_events_by_session_id(session_id: str, limit: int = 1000) -> List[Event]:
    """
    Get all events for a conversation/session.
    
    Args:
        session_id: Session/conversation ID
        limit: Maximum number of events to return
        
    Returns:
        List of Event instances ordered by timestamp
    """
    with DatabaseSession() as db_session:
        return db_session.query(Event).filter(
            Event.session_id == session_id
        ).order_by(Event.timestamp).limit(limit).all()


def get_first_user_event(session_id: str) -> Event | None:
    """
    Get the first user event in a session (for conversation title).
    
    Args:
        session_id: Session/conversation ID
        
    Returns:
        First user Event or None
    """
    with DatabaseSession() as db_session:
        return db_session.query(Event).filter(
            Event.session_id == session_id,
            Event.author == 'user'
        ).order_by(Event.timestamp).first()
