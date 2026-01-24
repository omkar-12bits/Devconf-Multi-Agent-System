import logging
import json
from typing import List, Optional

from a2a.types import Message as A2aMessage
from a2a.types import Part as A2aPart
from a2a.types import Task as A2aTask
from a2a.types import TaskState as A2aTaskState
from google.adk.events.event import Event
from google.adk.agents.callback_context import CallbackContext
from google.adk.sessions.session import Session
from google.genai.types import Content, Part
from orchestrator.apis.conversations.models import StreamEventData

from orchestrator.constants import RESPONSE_COLLECTION_AGENTS, DEFAULT_LANGUAGE, AgentNames

logger = logging.getLogger(__name__)

AGENT_PROGRESS_MESSAGES = {
    AgentNames.ROUTING_AGENT.value: "Routing your question...",
    AgentNames.GOOGLE_SEARCH_AGENT.value: "Searching Google...",
    AgentNames.GITHUB_AGENT.value: "Searching GitHub...",
}


def parse_preprocessing_output(preprocessed_output: str, fallback_query: str = "") -> tuple[str, str]:
    """Parse preprocessing output to extract language and query.
    """
    if not preprocessed_output or preprocessed_output.strip() == "":
        logger.warning("Empty preprocessing output")
        return DEFAULT_LANGUAGE, fallback_query
    
    lines = preprocessed_output.strip().split('\n', 1)
    
    detected_language = DEFAULT_LANGUAGE
    preprocessed_query = fallback_query if fallback_query else preprocessed_output
    
    if len(lines) >= 2 and lines[0].startswith("LANGUAGE:"):
        detected_language = lines[0].replace("LANGUAGE:", "").strip()
        preprocessed_query = lines[1].strip() if len(lines) > 1 else preprocessed_output
        logger.debug(f"Parsed: Language={detected_language}, Query={preprocessed_query[:50]}...")
    else:
        logger.warning("Output doesn't follow expected format (LANGUAGE: <lang>\\n<query>)")
        preprocessed_query = preprocessed_output.strip()
    
    return detected_language, preprocessed_query


def get_latest_user_message(events: List[Event]) -> str:
    """Extract the latest user message from a list of events.
    """
    if not events:
        logger.warning("No events available")
        return ""
    
    for event in reversed(events):
        if event.author == "user" and event.content and event.content.parts:
            user_message = event.content.parts[0].text
            logger.debug(f"Found user message: {user_message[:50]}...")
            return user_message
    
    logger.warning("No user message found in events")
    return ""


def determine_event_type_and_message(agent_name: str | None) -> tuple[str, str | None]:
    """Determine event type and progress message based on agent name.
    """
    if not agent_name or agent_name.strip() == "":
        logger.warning("Received empty or None agent_name in determine_event_type_and_message")
        return "progress", "Processing..."
    
    if agent_name == AgentNames.POSTPROCESS_AGENT.value:
        return "content", None
    
    if agent_name in AGENT_PROGRESS_MESSAGES:
        return "progress", AGENT_PROGRESS_MESSAGES[agent_name]
    
    return "progress", f"Processing ({agent_name})..."


def process_event_data(event: Event, conversation_id: str) -> StreamEventData:
    """Process an event and extract relevant content with event type classification.
    """
    event_type, progress_message = determine_event_type_and_message(event.author)
    
    # Extract response using A2A-aware extraction
    event_text = extract_a2a_response_from_event(event)
    event_thinking = extract_thinking_from_event(event)
    
    error_message = None
    if hasattr(event, "actions") and event.actions and event.actions.escalate:
        error_message = event.error_message or "Agent escalated"
    
    return StreamEventData(
        author=event.author,
        is_final=event.is_final_response(),
        conversation_id=conversation_id,
        message_id=event.invocation_id,
        event_type=event_type,
        progress_message=progress_message,
        content=event_text,
        thinking=event_thinking,
        error=error_message
    )


def extract_text_from_parts(parts: List[Part | A2aPart]) -> Optional[str]:
    """Extract text content from parts, ADK part or A2A part."""
    if not parts:
        return None

    parts_text = []
    for part in parts:
        if isinstance(part, Part) and part.thought:
            continue
        if isinstance(part, Part) and part.text:
            parts_text.append(part.text)
        elif isinstance(part, A2aPart) and part.root.kind == "text":
            parts_text.append(part.root.text)

    return "".join(parts_text)


def extract_thinking_from_event(event: Event) -> Optional[str]:
    """Extract thinking content from event, ADK event or A2A event."""
    if not event:
        return None
    # If this is an A2A response event, it does not contain thinking content
    if event.custom_metadata and event.custom_metadata.get("a2a:response"):
        return None

    parts_text = []
    if event.content and event.content.parts:
        for part in event.content.parts:
            if part.thought and part.text:
                parts_text.append(part.text)
    return "".join(parts_text)


def extract_a2a_response_from_event(event: Event) -> Optional[str]:
    """ Extract response text from an Event. Checks for A2A error first, then A2A response (in custom_metadata),
    then falls back to ADK event content.
    """

    if event.custom_metadata and (a2a_error := event.custom_metadata.get("a2a:error")):
        return a2a_error

    a2a_response = event.custom_metadata.get("a2a:response") if event.custom_metadata else None
    a2a_kind = a2a_response.get("kind") if a2a_response else None

    if a2a_kind == "task":
        task = A2aTask.model_validate(a2a_response)
        if task.artifacts:
            return extract_text_from_parts(task.artifacts[0].parts)
        elif task.status.message:
            return extract_text_from_parts(task.status.message.parts)

    elif a2a_kind == "message":
        message = A2aMessage.model_validate(a2a_response)
        return extract_text_from_parts(message.parts)

    # Fallback to ADK event's content
    elif event.content and event.content.parts:
        return extract_text_from_parts(event.content.parts)

    return None


def aggregate_events_text(event: Event, buffered_response_text: str, event_thinking: str) -> tuple[str, str]:
    """Extracts text from the event and concatenates it to the existing buffer,
    used for accumulating streaming responses across streaming events.
    """
    event_text = extract_a2a_response_from_event(event)
    event_text_thinking = extract_thinking_from_event(event)
    if event_text_thinking:
        event_thinking += event_text_thinking
    if event_text:
        buffered_response_text += event_text

    return buffered_response_text, event_thinking


def extract_text_parts_list(parts) -> list[str]:
    """
    Extract text from parts as a list, excluding thought parts.

    Skips parts that:
    - Don't have text
    - Have thought=True (includes parts where thought is False or None)

    Args:
        parts: The content parts to extract text from

    Returns:
        List of text strings from parts (excluding parts where thought=True)
    """
    return [
        part.text
        for part in parts
        if part.text and not part.thought
    ]


def extract_current_turn_response(callback_context: CallbackContext, agent_filter: list = None) -> str:
    """Extract ONLY the current turn's response from session events.
    
    Finds the most recent user message and collects agent responses after it.
    
    Args:
        callback_context: CallbackContext containing session with events
        agent_filter: List of agent names to collect responses from.
                     If None, uses RESPONSE_COLLECTION_AGENTS (default).
                     Pass specific agents like ["google_search_agent"] to filter.
        
    Returns:
        Complete aggregated response text for current turn only,
        or error message if errors occurred
    """
    try:
        session = callback_context.session
        
        if not session or not session.events:
            logger.warning("No session or events available")
            return "No session data available"
        
        agents_to_collect = agent_filter if agent_filter is not None else RESPONSE_COLLECTION_AGENTS
        
        last_user_message_index = -1
        for i in range(len(session.events) - 1, -1, -1):
            if session.events[i].author == "user":
                last_user_message_index = i
                break
        
        if last_user_message_index == -1:
            logger.warning("No user message found in session events")
            return "No user message found in conversation"
        
        logger.debug(f"Last user message at index {last_user_message_index}")
        
        response_parts = []
        error_messages = []
        
        for i in range(last_user_message_index + 1, len(session.events)):
            event = session.events[i]
            
            if hasattr(event, 'error_message') and event.error_message:
                error_messages.append(event.error_message)
                logger.error(f"Found error in event from {event.author}: {event.error_message}")
            
            if event.author in agents_to_collect:
                event_text = extract_a2a_response_from_event(event)
                
                if event_text:
                    if event_text.strip().startswith("For context:"):
                        logger.debug(f"Skipping context part from {event.author}")
                        continue
                    
                    response_parts.append(event_text)
                    logger.debug(f"Collected response from {event.author}: {len(event_text)} chars")
        
        if error_messages:
            error_response = " | ".join(error_messages)
            logger.error(f"Returning error message: {error_response}")
            return f"Error occurred: {error_response}"
        
        complete_response = "".join(response_parts)
        
        if not complete_response:
            logger.warning("No response content collected from current turn")
            return "No response generated from subagent"
        
        logger.info(f"Extracted {len(response_parts)} parts for CURRENT turn, total {len(complete_response)} chars")
        
        return complete_response
        
    except Exception as e:
        logger.error(f"Error extracting supervisor response: {e}", exc_info=True)
        return f"Error extracting response: {str(e)}"


def is_empty_event_for_submitted_task(event: Event) -> bool:
    if not event.custom_metadata:
        return False

    response: dict = event.custom_metadata.get("a2a:response", {})
    task_status_update: dict = response.get("status", {})
    task_state = task_status_update.get("state")

    if task_state == A2aTaskState.submitted:
        # Make sure submitted task didn't return any artifacts
        if response.get("artifacts"):
            return False
        # Make sure submitted task didn't return a message
        elif task_status_update.get("message"):
            return False
        return True
    else:
        return False


def merge_event_text_parts(events: list[Event]) -> Event:
    if not events:
        return None

    # Use the first event as the base event
    merged_event = events[0]

    # Collect all text parts from all events
    text_parts = []
    for event in events:
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    text_parts.append(part.text)

    if text_parts:
        joined_content = Content(
            role=merged_event.content.role,
            parts=[Part(text="".join(text_parts))]
        )
        merged_event.content = joined_content

    return merged_event


def _extract_agent_from_function_call(function_call) -> str | None:
    """Extract agent_name from a function_call object."""
    if not function_call or function_call.get('name') != 'transfer_to_agent':
        return None
    
    args = function_call.get('args', {})
    return args.get('agent_name')


def _extract_agent_from_orm_event(event) -> str | None:
    """Extract agent from ORM Event object (has .content as JSON string)."""
    if not (hasattr(event, 'content') and isinstance(event.content, (str, dict))):
        return None
    
    try:
        event_data = json.loads(event.content) if isinstance(event.content, str) else event.content
        
        if not event_data or event_data.get('role') == 'user':
            return None
        
        parts = event_data.get('parts', [])
        for part in parts:
            if not isinstance(part, dict) or 'function_call' not in part:
                continue
            
            agent_name = _extract_agent_from_function_call(part['function_call'])
            if agent_name:
                return agent_name
        
        return None
        
    except (json.JSONDecodeError, KeyError, TypeError):
        return None


def extract_sub_agent_name_from_events(events: List) -> str | None:
    """
    Extract which sub-agent was called from transfer_to_agent function calls.
    
    Args:
        events: List of ORM Event objects from database
        
    Returns:
        Agent name (e.g., "google_search_agent", "github_agent") or None if not found
    """
    for event in events:
        agent_name = _extract_agent_from_orm_event(event)
        if agent_name:
            logger.debug(f"Extracted agent from ORM event: {agent_name}")
            return agent_name
    
    # Fallback: string matching
    for event in events:
        try:
            event_str = str(event).lower()
            if "google_search_agent" in event_str:
                logger.debug("Found agent via string matching: google_search_agent")
                return "google_search_agent"
            elif "github_agent" in event_str:
                logger.debug("Found agent via string matching: github_agent")
                return "github_agent"
        except Exception:
            continue
    
    logger.debug("No agent found in events")
    return None
