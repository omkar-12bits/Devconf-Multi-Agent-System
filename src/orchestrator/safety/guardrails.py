"""
Content safety guardrails using OpenAI-compatible LLM (gpt-oss-120b).
"""
import json
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Literal, Optional
from uuid import UUID

import httpx
from langfuse import Langfuse
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from orchestrator.config import app_cfg
from orchestrator.constants import DEFAULT_LANGUAGE
from orchestrator.instructions import GUARDRAILS_INSTRUCTION

logger = logging.getLogger(__name__)


# Schema for structured JSON response from the guardrails model
class GuardrailResponseSchema(BaseModel):
    """JSON schema for guardrails response."""
    decision: Literal["SAFE", "UNSAFE"] = Field(description="Safety decision")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score 0.0-1.0")
    violation_type: Literal[
        "none", "dangerous_content", "hate_speech", 
        "explicit_content", "jailbreak", "malicious_intent"
    ] = Field(description="Violation type or 'none'")
    reasoning: str = Field(description="Brief explanation")
    detected_language: str = Field(description="Detected language of user input")


class GuardrailDecision(str, Enum):
    SAFE = "SAFE"
    UNSAFE = "UNSAFE"
    ERROR = "ERROR"


class ViolationType(str, Enum):
    NONE = "none"
    DANGEROUS_CONTENT = "dangerous_content"
    HATE_SPEECH = "hate_speech"
    EXPLICIT_CONTENT = "explicit_content"
    JAILBREAK = "jailbreak"
    MALICIOUS_INTENT = "malicious_intent"


@dataclass
class GuardrailResult:
    decision: GuardrailDecision
    confidence: float
    violation_type: ViolationType
    reasoning: str
    blocked: bool
    detected_language: Optional[str] = None


class GuardrailResultFactory:
    @staticmethod
    def safe() -> GuardrailResult:
        return GuardrailResult(
            decision=GuardrailDecision.SAFE,
            confidence=1.0,
            violation_type=ViolationType.NONE,
            reasoning="Content is safe",
            blocked=False,
            detected_language=DEFAULT_LANGUAGE
        )
    
    @staticmethod
    def error(error: str) -> GuardrailResult:
        return GuardrailResult(
            decision=GuardrailDecision.ERROR,
            confidence=0.0,
            violation_type=ViolationType.NONE,
            reasoning=f"Guardrails error: {error}",
            blocked=False,
            detected_language=DEFAULT_LANGUAGE
        )
    
    @staticmethod
    def blocked(
        violation_type: ViolationType,
        reasoning: str,
        confidence: float = 1.0,
        detected_language: Optional[str] = None
    ) -> GuardrailResult:
        return GuardrailResult(
            decision=GuardrailDecision.UNSAFE,
            confidence=confidence,
            violation_type=violation_type,
            reasoning=reasoning,
            blocked=True,
            detected_language=detected_language or DEFAULT_LANGUAGE
        )


def _parse_guardrail_response(response_text: str) -> GuardrailResult:
    """Parse the LLM response into a structured result."""
    try:
        data = json.loads(response_text)
        decision = GuardrailDecision(data.get("decision", "SAFE").upper())
        confidence = float(data.get("confidence", 1.0))
        violation_type_str = data.get("violation_type", "none").lower()
        reasoning = data.get("reasoning", "")
        detected_language = data.get("detected_language", DEFAULT_LANGUAGE)
        
        try:
            violation_type = ViolationType(violation_type_str)
        except ValueError:
            violation_type = ViolationType.NONE
        
        return GuardrailResult(
            decision=decision,
            confidence=confidence,
            violation_type=violation_type,
            reasoning=reasoning,
            blocked=False,
            detected_language=detected_language
        )
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse guardrails response as JSON: {e}")
        return GuardrailResultFactory.safe()
    except Exception as e:
        logger.warning(f"Error parsing guardrails response: {e}")
        return GuardrailResultFactory.safe()


async def check_content_safety(
    user_query: str,
    client: AsyncOpenAI,
) -> GuardrailResult:
    """Check content safety using the guardrails model."""    
    try:
        prompt = GUARDRAILS_INSTRUCTION.format(user_query=user_query)
        
        response = await client.chat.completions.create(
            model=app_cfg.GUARDRAILS_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        
        if not response.choices:
            return GuardrailResultFactory.safe()
        
        response_text = response.choices[0].message.content.strip()
        result = _parse_guardrail_response(response_text)
        
        if result.decision == GuardrailDecision.UNSAFE:
            result.blocked = result.confidence >= app_cfg.GUARDRAILS_CONFIDENCE_THRESHOLD
            
        return result
        
    except Exception as e:
        logger.error(f"Guardrails check failed: {e}")
        return GuardrailResultFactory.error(str(e))


async def apply_input_guard(
    prompt: str,
    session_id: str,
    message_id: UUID,
    langfuse_client: Langfuse,
) -> str:
    """Apply input guardrails and return prompt if safe, raise Exception if unsafe.

    Args:
        prompt: User input to check.
        session_id: Session ID for logging.
        message_id: Message ID for logging.
        langfuse_client: Langfuse client for tracing.

    Raises:
        Exception: If the content is blocked by guardrails.

    Returns:
        str: Unchanged user input if safe.
    """
    if not app_cfg.INPUT_GUARDRAILS_ENABLED:
        logger.info("Guardrails disabled via config - skipping safety checks")
        return prompt

    if not prompt or not prompt.strip():
        return prompt

    # Create async OpenAI client for guardrails
    client = AsyncOpenAI(
        base_url=app_cfg.OPENAI_COMPATIBLE_HOST,
        api_key=app_cfg.OPENAI_API_KEY,
        http_client=httpx.AsyncClient(verify=app_cfg.VERIFY_SSL, timeout=30),
    )

    with langfuse_client.start_as_current_observation(
        as_type="span", 
        name="content_safety_check", 
        input=prompt
    ) as span:
        try:
            result = await check_content_safety(prompt, client)
            
            span.update(output={
                "decision": result.decision.value,
                "confidence": result.confidence,
                "violation_type": result.violation_type.value,
                "reasoning": result.reasoning,
                "blocked": result.blocked,
                "detected_language": result.detected_language
            })
            
            if result.decision == GuardrailDecision.UNSAFE and result.blocked:
                raise Exception("I can't answer that. This query appears to violate our content policy. You can ask a question related to google search and github search.")
            return prompt
            
        except Exception as e:
            if "content policy" in str(e).lower() or "safety violation" in str(e).lower():
                raise
            logger.error(f"Guardrails check failed: {e}")
            span.update(output=str(e), level="ERROR")
            # On error, allow the request through (fail open)
            return prompt
