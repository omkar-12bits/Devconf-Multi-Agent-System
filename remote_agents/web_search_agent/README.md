# Google Search Agent (A2A Sample)

This is a sample Google Search agent built with Google ADK and exposed using the Agent-to-Agent (A2A) protocol.

## Prerequisites

- Python 3.10+
- `google-adk[a2a]` installed
- `uvicorn` installed
- `OPENAI_API_KEY` environment variable set

## Installation

```bash
pip install google-adk[a2a] uvicorn
```

## Running the Agent

You can run the agent server using the following command:

```bash
python -m remote_agents.web_search_agent.agent
```

Or directly with uvicorn:

```bash
uvicorn remote_agents.web_search_agent.agent:app --port 8001 --reload
```

## Usage

Once running, the agent will be accessible via the A2A protocol at `http://localhost:8001`.
