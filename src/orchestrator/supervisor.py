import logging

from orchestrator.config import app_cfg
from orchestrator.constants import AgentNames
from orchestrator.instructions import (
    PREPROCESSING_INSTRUCTION,
    ROUTING_AGENT_INSTRUCTION,
    POSTPROCESS_AGENT_INSTRUCTION,
    WEB_SEARCH_AGENT_DESCRIPTION,
    GITHUB_AGENT_DESCRIPTION
)
from orchestrator.summarizing_a2a_agent import SummarizingRemoteA2aAgent
from orchestrator.utils.app_utils import extract_current_turn_response, get_latest_user_message, parse_preprocessing_output
from orchestrator.utils.tracing_utils import LangfuseProvider
from orchestrator.safety.guardrails import apply_input_guard
from orchestrator.state_keys import StateKeys, StateDefaults, get_state_value, set_state_value

from google.adk.agents.llm_agent import Agent
from google.adk.agents import SequentialAgent
from google.adk.agents.callback_context import CallbackContext
from google.genai import Client, types
from google.adk.planners import BuiltInPlanner
from google.adk.models.lite_llm import LiteLlm

from openai import OpenAI

from openinference.instrumentation.google_adk import GoogleADKInstrumentor

logger = logging.getLogger(__name__)
GoogleADKInstrumentor().instrument()
langfuse = LangfuseProvider.get_client()


class SupervisorAgent:
    """Supervisor agent that routes queries to appropriate subagents using Google ADK native capability"""
    
    def __init__(self):
        """Initialize the supervisor agent with A2A subagents."""
        logger.info("Initializing SupervisorAgent...")
        
        self.app_cfg = app_cfg        
        self.extract_current_turn_response = extract_current_turn_response        
        self.model = LiteLlm(
            model=f"openai/{self.app_cfg.SUPERVISOR_MODEL}",
            api_base=self.app_cfg.OPENAI_COMPATIBLE_HOST,
            api_key=self.app_cfg.OPENAI_API_KEY
        )
        self.web_search_agent = self._create_a2a_agent(
            name=AgentNames.WEB_SEARCH_AGENT.value,
            description=WEB_SEARCH_AGENT_DESCRIPTION,
            agent_card_file=self.app_cfg.WEB_SEARCH_AGENT_CARD_FILE
        )
        
        self.github_agent = self._create_a2a_agent(
            name=AgentNames.GITHUB_AGENT.value,
            description=GITHUB_AGENT_DESCRIPTION,
            agent_card_file=self.app_cfg.GITHUB_AGENT_CARD_FILE
        )

        self.routing_agent = Agent(
            name=AgentNames.ROUTING_AGENT.value,
            model=self.model,
            instruction=ROUTING_AGENT_INSTRUCTION,
            sub_agents=[self.web_search_agent, self.github_agent],
            before_agent_callback=self.before_routing_callback,
            planner=BuiltInPlanner(
                thinking_config=types.ThinkingConfig(
                    include_thoughts=True,
                    thinking_budget=256,
                )
            )
        )
        
        self.preprocessing_agent = OpenAI(
            base_url=self.app_cfg.OPENAI_COMPATIBLE_HOST,
            api_key=self.app_cfg.OPENAI_API_KEY
        )
        
        self.postprocess_agent = Agent(
            name=AgentNames.POSTPROCESS_AGENT.value,
            model=self.model,
            instruction=POSTPROCESS_AGENT_INSTRUCTION,
            before_agent_callback=self.before_postprocess_callback,
            after_agent_callback=self.after_postprocess_callback
        )
        
        self.supervisor_agent = SequentialAgent(
            name=AgentNames.SUPERVISOR_AGENT.value,
            sub_agents=[
                self.routing_agent,
                self.postprocess_agent
            ]
        )
        
        logger.info(f"SupervisorAgent initialized!")
    
    async def before_routing_callback(self, callback_context: CallbackContext):
        """
        Callback before routing agent - performs guardrails check AND preprocessing.
        """
        StateDefaults.reset_query_state(callback_context.state)
        user_query = ""
        if callback_context.session and callback_context.session.events:
            user_query = get_latest_user_message(callback_context.session.events)
        
        if not user_query:
            logger.warning("No user query found")
            return None
        
        set_state_value(callback_context.state, StateKeys.ORIGINAL_QUERY, user_query)
        set_state_value(callback_context.state, StateKeys.PREPROCESSED_QUERY, user_query)
        
        if self.app_cfg.INPUT_GUARDRAILS_ENABLED:
            logger.info(f"Checking guardrails for query: {user_query[:100]}...")
            
            # Use optional span - automatically nests in parent trace context
            with langfuse.start_as_current_observation(as_type="guardrail", name="Guardrails Check", input=user_query) as span:
                try:
                    await apply_input_guard(
                        prompt=user_query,
                        session_id=callback_context.session.id,
                        message_id=callback_context.invocation_id,
                        langfuse_client=langfuse
                    )
                    logger.info("Guardrails passed - proceeding with preprocessing")
                    span.update(output="Passed")
                except Exception as e:
                    error_message = str(e)
                    logger.warning(f"Query BLOCKED by guardrails: {error_message}")
                    
                    set_state_value(callback_context.state, StateKeys.GUARDRAILS_FAILED, True)
                    set_state_value(callback_context.state, StateKeys.GUARDRAILS_ERROR_MESSAGE, error_message)
                    
                    span.update(output=f"Blocked: {error_message}", level="ERROR")
                    return types.Content(role="model", parts=[types.Part(text="")])
        else:
            logger.info("Guardrails disabled via config - skipping safety checks")
        
        logger.info("Preprocessing query (language detection + translation)...")

        # Use optional span - automatically nests in parent trace context
        with langfuse.start_as_current_observation(as_type="span", name="Preprocessing", input=user_query) as span:
            try:
                prompt = PREPROCESSING_INSTRUCTION.format(
                    user_query=user_query
                )            
                
                response = self.preprocessing_agent.chat.completions.create(
                    model=self.app_cfg.SUPERVISOR_MODEL,
                    messages=[{"role": "user", "content": prompt}]
                )
                
                detected_language, preprocessed_query = parse_preprocessing_output(
                    preprocessed_output=response.choices[0].message.content,
                    fallback_query=user_query
                )
                
                set_state_value(callback_context.state, StateKeys.DETECTED_LANGUAGE, detected_language)
                set_state_value(callback_context.state, StateKeys.PREPROCESSED_QUERY, preprocessed_query)
                
                logger.info(f"Preprocessing complete: {detected_language} → {preprocessed_query[:50]}...")
                
                span.update(output={
                    "original_query": user_query,
                    "detected_language": detected_language,
                    "preprocessed_query": preprocessed_query
                })
            except Exception as ex:
                logger.error(f"Preprocessing failed: {ex}", exc_info=True)
                span.update(output=str(ex), level="ERROR")

        logger.info(f"Proceeding with routing (Agent: {callback_context.agent_name})")
        return None
    
    async def before_postprocess_callback(self, callback_context: CallbackContext):
        """Callback before postprocess agent executes."""
        
        guardrails_failed = get_state_value(
            callback_context.state,
            StateKeys.GUARDRAILS_FAILED,
            StateDefaults.GUARDRAILS_FAILED
        )
        
        if guardrails_failed:
            error_message = get_state_value(
                callback_context.state,
                StateKeys.GUARDRAILS_ERROR_MESSAGE,
                StateDefaults.GUARDRAILS_ERROR_MESSAGE
            )
            logger.warning("Guardrails failed - returning error message to user")
            
            set_state_value(callback_context.state, StateKeys.ROUTING_AGENT_RESPONSE, error_message)
            detected_language = get_state_value(
                callback_context.state,
                StateKeys.DETECTED_LANGUAGE,
                StateDefaults.DETECTED_LANGUAGE
            )
            set_state_value(callback_context.state, StateKeys.DETECTED_LANGUAGE, detected_language)
            set_state_value(callback_context.state, StateKeys.FINAL_RESPONSE, error_message)
            return types.Content(
                role="model",
                parts=[types.Part(text=error_message)]
            )
        
        routing_agent_response = self.extract_current_turn_response(callback_context)        
        if not routing_agent_response or routing_agent_response.strip() == "":
            logger.error("Empty response from sub-agent - using fallback")
            routing_agent_response = "No response was generated from the subagent. Please try again or rephrase your question."
        
        logger.info(f"Response preview: {routing_agent_response[:100]}...")
        
        set_state_value(callback_context.state, StateKeys.ROUTING_AGENT_RESPONSE, routing_agent_response)
        
        return None
    
    async def after_postprocess_callback(self, callback_context: CallbackContext):
        """
        Callback after postprocess agent completes.
        Captures the final response in state for evaluation.
        """
        final_response = self.extract_current_turn_response(
            callback_context,
            agent_filter=[AgentNames.POSTPROCESS_AGENT.value]
        )
        
        if final_response:
            set_state_value(callback_context.state, StateKeys.FINAL_RESPONSE, final_response)
            logger.debug(f"Final response stored in state: {final_response[:100]}...")
        else:
            logger.warning("No final response captured")
        
        return None
    
    def _create_a2a_agent(self, name: str, description: str, agent_card_file: str) -> SummarizingRemoteA2aAgent:
        """Create a RemoteA2aAgent for A2A communication."""        
        return SummarizingRemoteA2aAgent(
            name=name,
            description=description,
            agent_card=agent_card_file,
        )


# Simple factory function
def create_supervisor() -> SupervisorAgent:
    """Create a supervisor agent instance.
    
    Returns:
        Initialized SupervisorAgent
    """
    return SupervisorAgent()
