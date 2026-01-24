import os
import uvicorn
from google.adk.agents.llm_agent import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.a2a.utils.agent_to_a2a import to_a2a

from remote_agents.google_search_agent.prompt import GOOGLE_SEARCH_AGENT_PROMPT

def create_agent():
    # Initialize the model
    # Ensure OPENAI_API_KEY is set in your environment
    model = LiteLlm(
        model=f"openai/{os.getenv("GOOGLE_SEARCH_AGENT_MODEL")}",
        api_base=os.getenv("OPENAI_COMPATIBLE_HOST"),
        api_key=os.getenv("GOOGLE_SEARCH_AGENT_API_KEY"),

    )
    
    # Create the agent
    agent = LlmAgent(
        name="google_search_agent",
        instruction=GOOGLE_SEARCH_AGENT_PROMPT,
        model=model
    )
    return agent

# Create the agent instance
agent = create_agent()

# Expose the agent using A2A
app = to_a2a(agent)

if __name__ == "__main__":
    # Run the agent server
    uvicorn.run(app, host="0.0.0.0", port=8001)
