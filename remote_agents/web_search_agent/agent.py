import logging
import os

import uvicorn
from google.adk.agents.llm_agent import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.a2a.utils.agent_to_a2a import to_a2a

from remote_agents.web_search_agent.prompt import WEB_SEARCH_AGENT_PROMPT
from remote_agents.web_search_agent.tools import search_web_tool

logger = logging.getLogger(__name__)


def create_agent():
    # Initialize the model
    model = LiteLlm(
        model=f"openai/{os.getenv("WEB_SEARCH_AGENT_MODEL")}",
        api_base=os.getenv("OPENAI_COMPATIBLE_HOST"),
        api_key=os.getenv("OPENAI_API_KEY"),
    )
    
    # Create the agent
    agent = LlmAgent(
        name="web_search_agent",
        instruction=WEB_SEARCH_AGENT_PROMPT,
        model=model,
        tools=[search_web_tool]
    )
    return agent

# Create the agent instance
agent = create_agent()
# Expose the agent using A2A
app = to_a2a(agent)

if __name__ == "__main__":
    # Run the agent server
    uvicorn.run(app, host="0.0.0.0", port=8001)
