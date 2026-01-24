"""
Session context management for A2A agent communication.

This module handles the extraction and summarization of session events,
converting them into concise context messages for remote agents.
"""
from enum import StrEnum
import logging

from a2a.types import Part as A2APart
from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from google.adk.flows.llm_flows.contents import _is_other_agent_reply
from google.genai import types as genai_types

from orchestrator.utils.app_utils import extract_text_parts_list, is_empty_event_for_submitted_task

logger = logging.getLogger(__name__)


class SessionContextBuilder:
    """Builds context summaries from session events for A2A communication."""

    def __init__(self, agent_name: str):
        """
        Initialize the context builder.

        Args:
            agent_name: Name of the current agent (used to identify boundaries)
        """
        self.agent_name = agent_name
        self.context_id = None
        self.all_messages = []
        self.current_agent_response = {"agent": None, "parts": []}

    def build_from_session(
        self, ctx: InvocationContext
    ) -> tuple[list[tuple[str, ...]], str]:
        """
        Extract messages from session events.

        Args:
            ctx: The invocation context containing session events

        Returns:
            Tuple of (all_messages, context_id):
            - all_messages: List of tuples representing user/agent messages
            - context_id: The context ID from the previous invocation
        """
        self._collect_messages_from_events(ctx)
        self._flush_remaining_response()
        self.all_messages.reverse()  # Convert to chronological order
        return self.all_messages, self.context_id

    def _collect_messages_from_events(self, ctx: InvocationContext) -> None:
        """
        Iterate backwards through events and collect messages.

        Args:
            ctx: The invocation context containing session events
        """
        for event in reversed(ctx.session.events):
            if self._is_boundary_event(event):
                break

            if not event.content or not event.content.parts:
                continue

            if is_empty_event_for_submitted_task(event):
                # Ignore A2A events for newly created task with `submitted` state,
                # these events can cause duplication of previous context messages
                continue

            if event.author == "user":
                self._process_user_message(event)
            elif _is_other_agent_reply(self.agent_name, event):
                self._process_agent_reply(event)

    def _is_boundary_event(self, event) -> bool:
        """
        Check if event marks the boundary of previous invocation.

        Args:
            event: The event to check

        Returns:
            True if this is a boundary event
        """
        if event.author == self.agent_name:
            if event.custom_metadata:
                self.context_id = event.custom_metadata.get("a2a:context_id")
            return True
        return False

    def _process_user_message(self, event) -> None:
        """
        Process a user message event.

        Args:
            event: The user message event
        """
        self._flush_agent_response()
        self.current_agent_response = {"agent": None, "parts": []}

        user_text = self._extract_text_from_parts(event.content.parts)
        if user_text:
            self.all_messages.append(("user", user_text))

    def _process_agent_reply(self, event) -> None:
        """
        Process an agent reply event (accumulates streaming responses).

        Args:
            event: The agent reply event
        """
        agent_name = event.author
        text_parts = extract_text_parts_list(event.content.parts)

        if not text_parts:
            return

        if self.current_agent_response["agent"] == agent_name:
            # Same agent - accumulate streaming chunks
            self.current_agent_response["parts"].extend(text_parts)
        else:
            # Different agent - flush previous and start new accumulation
            self._flush_agent_response()
            self.current_agent_response = {"agent": agent_name, "parts": text_parts}

    def _flush_agent_response(self) -> None:
        """Flush accumulated streaming agent response to messages list."""
        if (
            self.current_agent_response["agent"]
            and self.current_agent_response["parts"]
        ):
            # Reverse parts since we collected them backwards during iteration
            text = "".join(reversed(self.current_agent_response["parts"]))
            self.all_messages.append(
                ("agent", self.current_agent_response["agent"], text)
            )

    def _flush_remaining_response(self) -> None:
        """Flush any remaining accumulated response after iteration completes."""
        self._flush_agent_response()

    @staticmethod
    def _extract_text_from_parts(parts) -> str:
        """
        Extract and join text content from event parts.

        Args:
            parts: The content parts to extract text from

        Returns:
            Joined text content
        """
        text_parts = extract_text_parts_list(parts)
        return " ".join(text_parts) if text_parts else ""

class MessagePartType(StrEnum):
    USER_MESSAGE = "user_message"
    CONTEXT = "context"


class MessageFormatter:
    """Formats messages into A2A parts with context."""

    def __init__(self, genai_part_converter):
        """
        Initialize the formatter.

        Args:
            genai_part_converter: Function to convert genai parts to A2A parts
        """
        self.genai_part_converter = genai_part_converter

    def format_messages(
        self, all_messages: list[tuple[str, ...]]
    ) -> tuple[str, list[str]]:
        """
        Separate current message from historical context.

        Args:
            all_messages: List of message tuples (type, data...)

        Returns:
            Tuple of (current_user_message, context_messages)
        """
        current_user_message = ""
        context_messages = []

        if all_messages and all_messages[-1][0] == "user":
            current_user_message = all_messages[-1][1]
            # Format all previous messages as context
            for msg_type, *msg_data in all_messages[:-1]:
                if msg_type == "user":
                    context_messages.append(f"User previously asked: {msg_data[0]}")
                elif msg_type == "agent":
                    agent_name, agent_text = msg_data
                    context_messages.append(f"[{agent_name}] replied: {agent_text}")

        return current_user_message, context_messages

    def build_message_parts(
        self, current_user_message: str, context_messages: list[str]
    ) -> list[A2APart]:
        """
        Build final A2A message parts.

        Args:
            current_user_message: The current user's message
            context_messages: List of formatted context messages

        Returns:
            List of A2A message parts
        """
        message_parts = []


        if current_user_message:
            user_msg_part=self.genai_part_converter(genai_types.Part(text=current_user_message))
            user_msg_part.root.metadata = {
                "type": MessagePartType.USER_MESSAGE
            }
            message_parts.append(
                user_msg_part
            )

        if context_messages:
            context_text = "For context:\n" + "\n".join(context_messages)
            context_part=self.genai_part_converter(genai_types.Part(text=context_text))
            context_part.root.metadata = {
                 "type": MessagePartType.CONTEXT
            }
            message_parts.append(
                context_part
            )

        return message_parts


class CustomRemoteA2aAgent(RemoteA2aAgent):
    """
    Custom RemoteA2aAgent that uses our enhanced session context builder.

    This class overrides the default session context construction to provide
    LLM-based conversation summarization instead of sending all historical messages.
    """

    def _construct_message_parts_from_session(
        self, ctx: InvocationContext
    ) -> tuple[list[A2APart], str]:
        """
        Construct A2A message parts from session events with context summarization.

        This is the main entry point for converting session events into A2A message parts.
        It extracts user messages and agent replies, aggregates streaming responses,
        and creates a concise context summary.

        Args:
            self: The RemoteA2aAgent instance (provides name and genai_part_converter)
            ctx: The invocation context containing session events

        Returns:
            Tuple of (message_parts, context_id):
            - message_parts: List of A2A parts with current message and historical context
            - context_id: The context ID from the previous agent invocation
        """
        # Build context from session events
        builder = SessionContextBuilder(self.name)
        all_messages, context_id = builder.build_from_session(ctx)

        # Format messages into A2A parts
        formatter = MessageFormatter(self._genai_part_converter)
        current_message, context = formatter.format_messages(all_messages)
        message_parts = formatter.build_message_parts(current_message, context)

        logger.debug(f"MESSAGE PARTS: {[p.model_dump() for p in message_parts]}")
        return message_parts, context_id
