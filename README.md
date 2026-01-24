# DevConf Multi-Agent System

This project is a multi-agent system built with **Google ADK (Agent Development Kit)** and **FastAPI**. It features a supervisor orchestrator that intelligently routes user queries to specialized remote agents (Google Search and GitHub Search).

## 🚀 Features

- **Supervisor Agent**: Routes queries based on intent (Google Search vs. GitHub).
- **Remote Agents**: Specialized agents running as separate services via the Agent-to-Agent (A2A) protocol.
- **Input Guardrails**: Optional safety checks using Granite Guardian.
- **Session Management**: Supports both in-memory and database-backed conversation history.
- **Observability**: Integrated with Langfuse for tracing.

## 📋 Prerequisites

- **Python 3.13+**
- **Poetry** (Dependency Manager)
- **Google API Key** (for Gemini models)

## 🛠️ Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd Devconf-Multi-Agent-System
   ```

2. **Install dependencies:**
   ```bash
   poetry install
   ```

3. **Configure Environment Variables:**
   Copy the sample configuration file and update it with your credentials.
   ```bash
   cp .env.sample .env
   ```
   
   **Required Configuration:**
   - `GOOGLE_API_KEY`: Your Google Gemini API key.
   - `GOOGLE_SEARCH_AGENT_BASE_URL`: Set to `http://localhost:8001` for local development.
   - `GITHUB_AGENT_BASE_URL`: Set to `http://localhost:8002` for local development.

## 🏃‍♂️ Running the Application

The system consists of three separate services that need to be run simultaneously. You can run them in separate terminal windows.

### 1. Start the Google Search Agent (Port 8001)
```bash
poetry run uvicorn remote_agents.google_search_agent.agent:app --port 8001 --reload
```

### 2. Start the GitHub Search Agent (Port 8002)
```bash
poetry run uvicorn remote_agents.github_search_agent.agent:app --port 8002 --reload
```

### 3. Start the Orchestrator API (Port 8000)
```bash
poetry run uvicorn src.orchestrator.main:api --port 8000 --reload
```

## 📖 API Documentation

Once the Orchestrator is running, you can access the interactive API documentation (Swagger UI) at:

**http://localhost:8000/docs**

### Key Endpoints:
- **POST /api/devconf/v1/conversation**: Start a new conversation.
- **POST /api/devconf/v1/conversation/{id}/message**: Send a message to the agent.
- **GET /api/devconf/v1/meta/status**: Check the health of all system components.

## 🧪 Testing

You can test the system using the Swagger UI or `curl`.

**Example: Start a conversation**
```bash
curl -X 'POST' \
  'http://localhost:8000/api/devconf/v1/conversation' \
  -H 'accept: application/json' \
  -H 'user-id: test-user' \
  -d ''
```

**Example: Send a message**
```bash
curl -X 'POST' \
  'http://localhost:8000/api/devconf/v1/conversation/{conversation_id}/message' \
  -H 'accept: application/json' \
  -H 'user-id: test-user' \
  -H 'Content-Type: application/json' \
  -d '{
  "input": "Search Google for the latest news on AI agents",
  "stream": false
}'
```

## 🏗️ Project Structure

- `src/orchestrator`: Main API and Supervisor Agent logic.
- `remote_agents/`: Standalone agent services (Google Search, GitHub).
- `adk_web/`: Web interface components (if applicable).
