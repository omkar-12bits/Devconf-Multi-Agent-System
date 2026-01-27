import os
import uvicorn
from google.adk.agents.llm_agent import LlmAgent
from google.adk.tools import FunctionTool
from google.adk.models.lite_llm import LiteLlm
from google.adk.a2a.utils.agent_to_a2a import to_a2a

from remote_agents.github_search_agent.prompt import GITHUB_SEARGCH_AGENT_PROMPT
from remote_agents.github_search_agent.tools import get_repository_info, get_repository_languages, get_repository_contributors, get_repository_issues, get_repository_pulls, get_repository_releases, search_repositories

def create_agent():
    # Initialize the model
    # Ensure OPENAI_API_KEY is set in your environment
    model = LiteLlm(
        model=f"openai/{os.getenv("GITHUB_SEARCH_AGENT_MODEL")}",
        api_base=os.getenv("OPENAI_COMPATIBLE_HOST"),
        api_key=os.getenv("OPENAI_API_KEY"),

    )
    
    # Create the agent
    agent = LlmAgent(
        name="github_search_agent",
        instruction=GITHUB_SEARGCH_AGENT_PROMPT,
        model=model,
        tools=[FunctionTool(func=get_repository_info), FunctionTool(func=get_repository_languages), FunctionTool(func=get_repository_contributors),
        FunctionTool(func=get_repository_issues), FunctionTool(func=get_repository_pulls), FunctionTool(func=get_repository_releases), FunctionTool(func=search_repositories)
        ]
    )
    return agent

# Create the agent instance
agent = create_agent()
# Expose the agent using A2A
app = to_a2a(agent)

if __name__ == "__main__":
    # Run the agent server
    uvicorn.run(app, host="0.0.0.0", port=8002)
