import logging
from typing import Optional, Tuple

from a2a.types import Part as A2APart
from a2a.types import TextPart as A2ATextPart
from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.remote_a2a_agent import (A2A_METADATA_PREFIX,
                                                RemoteA2aAgent,
                                                _is_other_agent_reply)
from google.adk.events.event import Event
from google.genai import Client, types

from .session_context import MessagePartType
from orchestrator.config import app_cfg
from orchestrator.utils.app_utils import is_empty_event_for_submitted_task, merge_event_text_parts
from orchestrator.state_keys import StateKeys
from orchestrator.instructions import CONTEXT_SUMMARIZATION_PROMPT
from openai import OpenAI

logger = logging.getLogger(__name__)

SUMMARIZATION_MIN_CHARS = 2000
A2A_INCLUDED_EVENT_AUTHORS = ["user"]
CONTEXT_SUMMARIZATION_MODEL = "openai/gpt-oss-20b"
OUTPUT_DELIMITER = "###USER INPUT###"


class ContextSummarizer:
    def __init__(self, model: str, prompt: str = CONTEXT_SUMMARIZATION_PROMPT):
        self._model = model
        self._prompt = prompt
        self._app_cfg = app_cfg
        self._openai_client = OpenAI(
            base_url=self._app_cfg.OPENAI_COMPATIBLE_HOST,
            api_key=self._app_cfg.OPENAI_API_KEY
        )
    
    def _should_summarize(
        self,
        message_parts: list[A2APart]
    ) -> tuple[bool, str]:
        """
        Determine if summarization is needed based on context size.
        
        Returns:
            tuple[bool, str]: (should_summarize, reason)
        """
        if len(message_parts) <= 1:
            return False, "message_parts_too_short"
        
        total_chars = sum(
            len(part.root.text) 
            for part in message_parts 
            if part.root.kind == "text" and part.root.text
        )
        
        if total_chars < SUMMARIZATION_MIN_CHARS:
            return False, "small_context"
        
        return True, "summarize"

    def summarize_message_parts(
        self,
        message_parts: list[A2APart]
    ) -> list[A2APart]:
        """
        Conditionally summarize message parts based on context size.
        """
        should_summarize, reason = self._should_summarize(message_parts)
        
        if not should_summarize:
            logger.info(f"Skipping summarization: {reason}")
            return self._mark_user_message_part(message_parts)
        
        logger.info(f"Applying summarization: {reason}")

        try:
            conversation_history = []
            last_user_input = message_parts[-1].root.text

            for part in message_parts[:-1]:
                if part.root.text:
                    conversation_history.append(part.root.text)

            if not conversation_history:
                logger.warning("No conversation history found after filtering, skipping summarization")
                return self._mark_user_message_part(message_parts)

            conversation_history_text = "\n---\n".join(conversation_history)

            prompt = self._prompt.format(
                conversation_history_text=conversation_history_text,
                last_user_input=last_user_input
            )

            response = self._openai_client.chat.completions.create(
                model=self._app_cfg.PREPROCESSING_MODEL,
                messages=[{"role": "user", "content": prompt}]
            )

            if response.choices[0].message.content:
                updated_parts = []
                user_message, summarized_context = self._parse_summarized_response(response.choices[0].message.content)

                if summarized_context:
                    context_part = A2APart(root=A2ATextPart(
                        kind="text",
                        text=summarized_context,
                        metadata={"type": MessagePartType.CONTEXT})
                    )
                    updated_parts.append(context_part)

                user_message_part = A2APart(root=A2ATextPart(
                    kind="text",
                    text=user_message,
                    metadata={"type": MessagePartType.USER_MESSAGE})
                )
                updated_parts.append(user_message_part)

                return updated_parts
            else:
                logger.warning("Empty response from summarization LLM, using original parts")
                return self._mark_user_message_part(message_parts)

        except Exception as e:
            logger.error(f"Error during message parts summarization: {str(e)}", exc_info=True)
            logger.warning("Falling back to original parts")
            return self._mark_user_message_part(message_parts)

    def _parse_summarized_response(
        self,
        response_text: str
    ) -> Tuple[str, str | None]:
        """Parse LLM summarized response into user message and context.
        
        Returns:
            Tuple[str, str | None]: (user_message, summarized_context)
        """
        logger.info(f"A2A Context Summarized and Rephrased Input:\n{response_text}")

        if OUTPUT_DELIMITER not in response_text:
            # Parsing failed, return full response as user message
            logger.warning(f"Failed to parse summarized response, missing '{OUTPUT_DELIMITER}' delimiter")
            return response_text, None

        summarized_context, user_message = response_text.split(OUTPUT_DELIMITER, 1)
        # If still can't parse user message, return full response as user message
        if not user_message:
            return response_text, None

        user_message = user_message.strip()
        summarized_context = summarized_context.strip()
        return user_message, summarized_context

    def _mark_user_message_part(
        self,
        parts: list[A2APart]
    ) -> list[A2APart]:
        """Structure message parts without LLM summarization."""
        if not parts:
            return parts

        if len(parts) == 1:
            if parts[0].root.kind == "text":
                parts[0].root.metadata = {"type": MessagePartType.USER_MESSAGE}
            return parts
        
        updated_parts = []
        
        last_part = parts[-1]
        if last_part.root.kind == "text" and last_part.root.text:
            user_message_part = A2APart(root=A2ATextPart(
                kind="text",
                text=last_part.root.text,
                metadata={"type": MessagePartType.USER_MESSAGE}
            ))
            
            context_messages = []
            for part in parts[:-1]:
                if part.root.kind == "text" and part.root.text:
                    context_messages.append(part.root.text)

            if context_messages:
                context_text = "Context Summary:\n" + "\n---\n".join(context_messages)
                context_part = A2APart(root=A2ATextPart(
                    kind="text",
                    text=context_text,
                    metadata={"type": MessagePartType.CONTEXT}
                ))
                updated_parts.append(context_part)
            
            updated_parts.append(user_message_part)
            return updated_parts
        
        # Fallback: return original parts if unexpected structure
        return parts


class SummarizingRemoteA2aAgent(RemoteA2aAgent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._context_summarizer = ContextSummarizer(CONTEXT_SUMMARIZATION_MODEL)

    def _construct_message_parts_from_session(
        self,
        ctx: InvocationContext
    ) -> tuple[list[A2APart], str]:
        message_parts: list[A2APart] = []
        context_id = None
        events_to_process: list[Event] = []
        
        preprocessed_query = ctx.session.state.get(StateKeys.PREPROCESSED_QUERY.value, "")       
        
        for event in reversed(ctx.session.events):
            if event.author == self.name:
                if event.custom_metadata:
                    context_id = event.custom_metadata.get(A2A_METADATA_PREFIX + "context_id")
                break
            
            # Filter events: include user messages and A2A responses, skip internal orchestration
            is_user_message = event.author in A2A_INCLUDED_EVENT_AUTHORS
            is_a2a_response = (
                event.custom_metadata and 
                A2A_METADATA_PREFIX + "context_id" in event.custom_metadata
            )
            
            if is_user_message or is_a2a_response:
                events_to_process.append(event)

        if preprocessed_query:
            logger.info(f"Using preprocessed query from state for A2A request: {preprocessed_query[:50]}...")
            
            for i, event in enumerate(events_to_process):
                if event.author == "user":
                    original_text = ""
                    if event.content and event.content.parts:
                        for part in event.content.parts:
                            if part.text:
                                original_text = part.text
                                break
                    
                    if original_text.strip() != preprocessed_query.strip():
                        events_to_process[i] = Event(
                            timestamp=event.timestamp,
                            author="user",
                            content=types.Content(parts=[types.Part(text=preprocessed_query)]),
                            branch=event.branch,
                            invocation_id=event.invocation_id
                        )
                    break

        consolidated_events = self._consolidate_agent_task_events(reversed(events_to_process))

        for event in consolidated_events:
            if _is_other_agent_reply(self.name, event):
                event = self._present_other_agent_message(event)

            if not event or not event.content or not event.content.parts:
                continue

            for part in event.content.parts:
                converted_part = self._genai_part_converter(part)
                if converted_part:
                    message_parts.append(converted_part)
                else:
                    logger.warning("Failed to convert part to A2A format: %s", part)

        message_parts = self._context_summarizer.summarize_message_parts(message_parts)

        logger.info(f"Sending {len(message_parts)} message parts to A2A agent with context_id={context_id}")

        return message_parts, context_id

    def _present_other_agent_message(
        self,
        event: Event
    ) -> Optional[Event]:
        if not event.content or not event.content.parts:
            return event

        content = types.Content(role=event.content.role, parts=[])
        for part in event.content.parts:
            if part.thought:
                continue
            elif part.text:
                content.parts.append(
                    types.Part(text=f"[{event.author}] said: {part.text}")
                )
            else:
                continue

        if not content.parts:
            return None

        return Event(
            timestamp=event.timestamp,
            author=event.author,
            content=content,
            branch=event.branch,
        )

    def _consolidate_agent_task_events(
        self,
        events: list[Event]
    ) -> list[Event]:
        if not events:
            return []

        processed_events: list[Event] = []
        same_task_events: list[Event] = []
        current_agent = None
        current_task_id = None

        for event in events:
            if is_empty_event_for_submitted_task(event):
                continue

            agent_name = event.author
            task_id = None
            if event.custom_metadata:
                task_id = event.custom_metadata.get(A2A_METADATA_PREFIX + "task_id")

            should_consolidate = (
                task_id is not None
                and task_id == current_task_id
                and current_agent == agent_name
            )

            if should_consolidate:
                same_task_events.append(event)
            else:
                if same_task_events:
                    processed_events.append(merge_event_text_parts(same_task_events))

                if task_id is not None:
                    same_task_events = [event]
                    current_agent = agent_name
                    current_task_id = task_id
                else:
                    processed_events.append(event)
                    same_task_events = []
                    current_agent = None
                    current_task_id = None

        if same_task_events:
            processed_events.append(merge_event_text_parts(same_task_events))

        return processed_events
