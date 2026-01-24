import json
import logging
from typing import List

from orchestrator.config import app_cfg
from orchestrator.apis.history.models import SessionSummary, SessionDetail, ConversationTurn
from orchestrator.constants import AgentNames
from orchestrator.db.sessions.crud import get_sessions_by_user_id, get_session_by_id
from orchestrator.db.events.crud import get_events_by_session_id, get_first_user_event

logger = logging.getLogger(__name__)


class HistoryService:
    """Service for retrieving conversation history from database."""
    
    def __init__(self):
        """Initialize history service."""
        logger.info("HistoryService initialized")
    
    def get_user_sessions(
        self, 
        user_id: str, 
        limit: int = 10
    ) -> List[SessionSummary]:
        """Get conversation session summaries for a user (without full conversation turns)."""
        try:
            session_models = get_sessions_by_user_id(user_id, limit)
            
            sessions = []
            for session_model in session_models:
                first_event = get_first_user_event(session_model.id)
                title = self._extract_title_from_event(first_event)
                
                user_events = get_events_by_session_id(session_model.id)
                turn_count = len([e for e in user_events if e.author == 'user'])
                
                session_summary = SessionSummary(
                    conversation_id=session_model.id,
                    user_id=session_model.user_id,
                    title=title,
                    created_at=session_model.create_time,
                    updated_at=session_model.update_time,
                    turn_count=turn_count
                )
                
                sessions.append(session_summary)
            
            logger.info(f"Retrieved {len(sessions)} sessions for user {user_id}")
            return sessions
                
        except Exception as e:
            logger.error(f"Error fetching user sessions: {e}", exc_info=True)
            return []
    
    def get_session_detail_by_id(
        self, 
        session_id: str,
        user_id: str
    ) -> SessionDetail | None:
        """Get a specific session with full conversation turns."""
        try:
            session_model = get_session_by_id(session_id, user_id)
            
            if not session_model:
                logger.warning(f"Session {session_id} not found for user {user_id}")
                return None
            
            first_event = get_first_user_event(session_model.id)
            title = self._extract_title_from_event(first_event)
            
            events = get_events_by_session_id(session_model.id)
            turns = self._get_session_turns(events, session_model.id)
            
            turn_count = len([e for e in events if e.author == 'user'])
            
            return SessionDetail(
                conversation_id=session_model.id,
                user_id=session_model.user_id,
                title=title,
                created_at=session_model.create_time,
                updated_at=session_model.update_time,
                turn_count=turn_count,
                turns=turns
            )
                
        except Exception as e:
            logger.error(f"Error fetching session {session_id}: {e}", exc_info=True)
            return None
    
    def _extract_title_from_event(self, event) -> str:
        """
        Extract title from first user event.
        
        Args:
            event: First user Event from database
            
        Returns:
            Formatted title string
        """
        if not event or not event.content:
            return "Untitled Conversation"
        
        try:
            content_json = json.loads(event.content) if isinstance(event.content, str) else event.content
            if content_json and 'parts' in content_json:
                for part in content_json['parts']:
                    if part.get('text'):
                        return part['text'].strip()
        except (json.JSONDecodeError, KeyError, TypeError):
            pass
        
        return "Untitled Conversation"
    
    def _get_session_turns(self, events: List, session_id: str) -> List[ConversationTurn]:
        """
        Extract conversation turns (Q&A pairs) from events.
        
        Args:
            events: List of Event objects (from ORM)
            session_id: Session/conversation ID
            
        Returns:
            List of ConversationTurn objects
        """
        try:
            turns = []
            current_question = None
            current_timestamp = None
            current_message_id = None
            responses = []
            thinking_content = []
            
            for event in events:
                author = event.author
                
                if author not in ["user", AgentNames.POSTPROCESS_AGENT.value, AgentNames.ROUTING_AGENT.value]:
                    continue
                
                content_text, thought_text = self._extract_text_and_thinking_from_event(event)
                
                if author == "user":
                    if current_question and responses and current_message_id:
                        answer = self._combine_responses(responses)
                        thinking = self._combine_responses(thinking_content) if thinking_content else None
                        turns.append(ConversationTurn(
                            conversation_id=session_id,
                            message_id=current_message_id,
                            question=current_question,
                            answer=answer,
                            thinking=thinking,
                            timestamp=current_timestamp
                        ))
                    
                    # Start new turn
                    current_question = content_text
                    current_timestamp = event.timestamp
                    current_message_id = event.invocation_id
                    responses = []
                    thinking_content = []
                
                elif author in [AgentNames.POSTPROCESS_AGENT.value, AgentNames.ROUTING_AGENT.value]:
                    if content_text:
                        responses.append(content_text)
                    if thought_text:
                        thinking_content.append(thought_text)
            
            # Add last turn
            if current_question and responses and current_message_id:
                answer = self._combine_responses(responses)
                thinking = self._combine_responses(thinking_content) if thinking_content else None
                turns.append(ConversationTurn(
                    conversation_id=session_id,
                    message_id=current_message_id,
                    question=current_question,
                    answer=answer,
                    thinking=thinking,
                    timestamp=current_timestamp
                ))
            
            logger.debug(f"Extracted {len(turns)} turns from {len(events)} events")
            return turns
            
        except Exception as e:
            logger.error(f"Error extracting session turns: {e}", exc_info=True)
            return []
    
    def _extract_text_and_thinking_from_event(self, event) -> tuple[str, str]:
        """
        Extract both text content and thinking/reasoning from an event.
        
        Args:
            event: Database event row
            
        Returns:
            Tuple of (content_text, thinking_content)
        """
        content_text = ""
        thinking_text = ""
        
        if event.content:
            try:
                content_json = json.loads(event.content)
                if 'parts' in content_json and content_json['parts']:
                    for part in content_json['parts']:
                        if part.get('thought') and part.get('text'):
                            thinking_text = part['text'].strip()
                        elif part.get('text'):
                            content_text = part['text'].strip()
            except json.JSONDecodeError:
                logger.debug("Failed to parse event content as JSON")
        
        if not content_text and event.custom_metadata:
            try:
                metadata = json.loads(event.custom_metadata)
                if 'a2a:response' in metadata:
                    a2a_resp = metadata['a2a:response']
                    if a2a_resp.get('kind') == 'message' and 'parts' in a2a_resp:
                        for part in a2a_resp['parts']:
                            if part.get('kind') == 'text':
                                content_text = part.get('text', '')
                                break
            except json.JSONDecodeError:
                logger.debug("Failed to parse custom_metadata as JSON")
        
        return content_text, thinking_text
    
    def _combine_responses(self, responses: List[str]) -> str:
        """
        Combine multiple response chunks into a single answer.
        
        Args:
            responses: List of response chunks
            
        Returns:
            Combined response string
        """
        seen = set()
        unique_responses = []
        
        for response in responses:
            if not response or not response.strip():
                continue
            
            if len(response) < 50:
                if response in seen:
                    continue
                seen.add(response)
            
            unique_responses.append(response)
        
        return " ".join(unique_responses).strip()


# Singleton instance
_history_service_instance = None


def get_history_service() -> HistoryService:
    """Get or create history service singleton instance."""
    global _history_service_instance
    
    if _history_service_instance is None:
        if not (app_cfg.DATABASE_URL and app_cfg.USE_DATABASE_SESSIONS):
            raise ValueError(
                "Database not configured or disabled. "
                "Please enable database session storage (USE_DATABASE_SESSIONS=True and DATABASE_URL set) to use history feature."
            )
        _history_service_instance = HistoryService()
    
    return _history_service_instance

