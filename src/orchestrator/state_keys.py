from enum import Enum
from typing import Any
from orchestrator.constants import DEFAULT_LANGUAGE

class StateKeys(str, Enum):
    """Centralized state keys used across all agents in the orchestrator."""
    
    GUARDRAILS_FAILED = "guardrails_failed"
    GUARDRAILS_ERROR_MESSAGE = "guardrails_error_message"
    ORIGINAL_QUERY = "original_query"
    DETECTED_LANGUAGE = "detected_language"
    PREPROCESSED_QUERY = "preprocessed_query"
    ROUTING_AGENT_RESPONSE = "routing_agent_response"
    FINAL_RESPONSE = "final_response"

class StateDefaults:
    """Default values for state keys."""
    
    GUARDRAILS_FAILED: bool = False
    GUARDRAILS_ERROR_MESSAGE: str = ""
    ORIGINAL_QUERY: str = ""
    DETECTED_LANGUAGE: str = DEFAULT_LANGUAGE
    PREPROCESSED_QUERY: str = ""
    ROUTING_AGENT_RESPONSE: str = ""
    FINAL_RESPONSE: str = ""    
    
    @classmethod
    def get_default(cls, state_key: StateKeys) -> Any:
        """Get default value for a state key."""
        defaults_map = {
            StateKeys.GUARDRAILS_FAILED: cls.GUARDRAILS_FAILED,
            StateKeys.GUARDRAILS_ERROR_MESSAGE: cls.GUARDRAILS_ERROR_MESSAGE,
            StateKeys.ORIGINAL_QUERY: cls.ORIGINAL_QUERY,
            StateKeys.DETECTED_LANGUAGE: cls.DETECTED_LANGUAGE,
            StateKeys.PREPROCESSED_QUERY: cls.PREPROCESSED_QUERY,
            StateKeys.ROUTING_AGENT_RESPONSE: cls.ROUTING_AGENT_RESPONSE,
            StateKeys.FINAL_RESPONSE: cls.FINAL_RESPONSE
        }
        
        return defaults_map.get(state_key, None)
    
    @classmethod
    def reset_query_state(cls, state: dict) -> None:
        """Reset query-specific state to default values."""
        set_state_value(state, StateKeys.GUARDRAILS_FAILED, cls.GUARDRAILS_FAILED)
        set_state_value(state, StateKeys.GUARDRAILS_ERROR_MESSAGE, cls.GUARDRAILS_ERROR_MESSAGE)
        set_state_value(state, StateKeys.ORIGINAL_QUERY, cls.ORIGINAL_QUERY)
        set_state_value(state, StateKeys.DETECTED_LANGUAGE, cls.DETECTED_LANGUAGE)
        set_state_value(state, StateKeys.PREPROCESSED_QUERY, cls.PREPROCESSED_QUERY)
        set_state_value(state, StateKeys.ROUTING_AGENT_RESPONSE, cls.ROUTING_AGENT_RESPONSE)
        set_state_value(state, StateKeys.FINAL_RESPONSE, cls.FINAL_RESPONSE)


def get_state_value(state: dict, key: StateKeys, default: Any = None) -> Any:
    """Helper function to safely get state value with default."""
    if default is None:
        default = StateDefaults.get_default(key)
    
    return state.get(key.value, default)


def set_state_value(state: dict, key: StateKeys, value: Any) -> None:
    """Helper function to set state value using enum key."""
    state[key.value] = value

