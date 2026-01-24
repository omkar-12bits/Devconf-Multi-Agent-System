# File copied from ifd/core/safety/guardrails.py
import asyncio
import logging
from typing import List, Tuple
from uuid import UUID

import httpx
from langfuse import Langfuse
from openai import AsyncOpenAI
from openai.types.chat.chat_completion import ChatCompletion

from orchestrator.config import app_cfg
from orchestrator.safety.guardrails_types import RiskProbability
from orchestrator.safety.granite_guardian_helpers import parse_output
from orchestrator.safety.canned_responses import PredefinedResponses

logger = logging.getLogger(__name__)


_guardian_client: AsyncOpenAI = AsyncOpenAI(
    base_url=app_cfg.GRANITE_GUARDIAN_HOST,
    api_key=app_cfg.GRANITE_GUARDIAN_API_KEY,
    http_client=httpx.AsyncClient(verify=False, timeout=10),
)

GRANITE_GUARDIAN_RISK_THRESHOLD: float = 0.80
GRANITE_GUARDIAN_LEETSPEAK_THRESHOLD: float = 0.65
GRANITE_GUARDIAN_ROLEPLAY_THRESHOLD: float = 0.65
GRANITE_GUARDIAN_AMNESIA_THRESHOLD: float = 0.65


ROLEPLAY_JAILBREAK_RISK_NAME = "Roleplay Jailbreak"
ROLEPLAY_JAILBREAK_RISK_DEFINITION = "User attempts to make the AI impersonate a specific character or entity (e.g., 'Dr. House', 'dead granny'). This is a risk as it often aims to circumvent safety guidelines or generate restricted content."

LEET_SPEAK_RISK_NAME = "Leet Speak"
LEET_SPEAK_RISK_DEFINITION = "User engages in leetspeak or attempts to coerce model to output leetspeak"

AMNESIA_RISK_NAME = "Amnesia Risk"
AMNESIA_RISK_DEFINITION = "User tricks the model to forget any instructions."

RISK_THRESHOLDS = {
    LEET_SPEAK_RISK_NAME: GRANITE_GUARDIAN_LEETSPEAK_THRESHOLD,
    ROLEPLAY_JAILBREAK_RISK_NAME: GRANITE_GUARDIAN_ROLEPLAY_THRESHOLD,
    AMNESIA_RISK_NAME: GRANITE_GUARDIAN_AMNESIA_THRESHOLD,
}


async def _check_single_risk(
    prompt: str,
    risk_name: str,
    risk_definition: str,
    session_id: str,
    message_id: UUID,
    langfuse_client: Langfuse,
) -> Tuple[str, RiskProbability | None, Exception | None]:
    """Check a single risk category.

    Args:
        prompt: User input to check
        risk_name: Name of the risk category
        risk_definition: Definition of the risk category
        session_id: Llama Stack session Id
        message_id: Message Id for user input

    Returns:
        Tuple of (risk_name, verdict or None, exception or None)
    """
    with langfuse_client.start_as_current_observation(as_type="span", name=risk_name, input=prompt) as span:
        try:
            guardian_config = {
                "guardian_config": {
                    "risk_name": risk_name,
                    "risk_definition": risk_definition,
                }
            }

            guardian_resp: ChatCompletion = await _guardian_client.chat.completions.create(
                model=app_cfg.GRANITE_SHIELD_ID,
                temperature=0.0,
                logprobs=True,
                top_logprobs=20,
                messages=[{"role": "user", "content": prompt}],
                extra_body={
                    "chat_template_kwargs": guardian_config,
                },
            )

            verdict = parse_output(guardian_resp)
            span.update(output=verdict)
            return (risk_name, verdict, None)
        # Throw Value Error if parse_output fails for whatever reason
        except ValueError as e:
            logger.error(
                f"Guardian parse error for {risk_name}: {e} ls_session_id={session_id} message_id={message_id}"
            )
            span.update(output=str(e), level="ERROR")
            return (risk_name, None, e)
        # Log error but don't stop the flow if request failed since we are running in parallel
        except Exception as exc:
            logger.exception(
                f"Guardian request failed for {risk_name}: ls_session_id={session_id} message_id={message_id}"
            )
            span.update(output=str(exc), level="ERROR")
            return (risk_name, None, exc)


async def apply_input_guard(
    prompt: str,
    session_id: str,
    message_id: UUID,
    langfuse_client: Langfuse,
) -> str:
    """Applies the input safety with Granite Guardian and return it unchanged or
    raise SafetyViolationError exception when the request is deemed 'harm'.

    Args:
        prompt (str): User input.
        session_id (str): Llama Stack session Id.
        message_id (UUID): Message Id for user input.

    Raises:
        SafetyViolationError: Safety violation error.

    Returns:
        str: Unchanged user input.
    """

    if not app_cfg.GRANITE_GUARDIAN_HOST or not app_cfg.GRANITE_GUARDIAN_API_KEY or not app_cfg.GRANITE_SHIELD_ID:
        logger.warning("Guardian host, shield, or API key is not configured, skipping input guard")
        return prompt

    risk_categories = [
        (ROLEPLAY_JAILBREAK_RISK_NAME, ROLEPLAY_JAILBREAK_RISK_DEFINITION),
        (LEET_SPEAK_RISK_NAME, LEET_SPEAK_RISK_DEFINITION),
        (AMNESIA_RISK_NAME, AMNESIA_RISK_DEFINITION),
    ]


    # Run risk checks in parallel
    check_tasks = [
        _check_single_risk(prompt, risk_name, risk_definition, session_id, message_id, langfuse_client)
        for risk_name, risk_definition in risk_categories
    ]

    results = await asyncio.gather(*check_tasks)


    # Process results and populate safety_checks list
    violations: List[Tuple[str, RiskProbability]] = []
    guardian_unavailable = False

    for risk_name, verdict, error in results:
        if error is not None:
            guardian_unavailable = True
            continue

        # Record all successful checks in the safety_checks list
        if verdict:
            threshold = RISK_THRESHOLDS.get(risk_name, GRANITE_GUARDIAN_RISK_THRESHOLD)

            # Check if this is a violation
            if verdict.is_risky and verdict.risky_confidence >= threshold:
                violations.append((risk_name, verdict))

    # If any guardian calls failed and we don't have at least one successful check, fail safe and throw error
    # A successful check is one where the result's 3rd value (the error) is None
    # 'result' Tuple: (risk_name, verdict, error)
    successful_checks = [result for result in results if result[2] is None]
    all_checks_failed = len(successful_checks) == 0
    if guardian_unavailable and all_checks_failed:
        raise Exception(PredefinedResponses.GUARDIAN_UNAVAILABLE_MESSAGE)

    # If we have multiple violations, raise error for the most confident one
    if violations:
        # Sort by calculated confidence value and take the highest
        violations.sort(key=lambda violation: violation[1].risky_confidence, reverse=True)
        most_severe_risk_name, most_severe_verdict = violations[0]

        logger.error(
            f"Safety Violation: violation_type={most_severe_risk_name} "
            f"confidence={most_severe_verdict.risky_confidence} "
            f"threshold={RISK_THRESHOLDS.get(most_severe_risk_name, GRANITE_GUARDIAN_RISK_THRESHOLD)} "
            f"ls_session_id={session_id} message_id={message_id} "
        )
        
        # Raise with user-friendly canned response
        raise Exception(PredefinedResponses.DEFAULT_SAFETY_VIOLATION_MESSAGE)
    
    logger.info(f"Input guard passed for message content: {prompt}, results: {results}")
    return prompt


