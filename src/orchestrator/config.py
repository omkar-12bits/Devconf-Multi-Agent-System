from pydantic_settings import BaseSettings
from pydantic import field_validator


class ApiConfig(BaseSettings):
    # Application Configuration
    APP_NAME: str = "devconf_multi_agent"
    API_ROUTER_PATH_PREFIX: str = "/api/devconf/v1"

    # supervisor model configuration
    SUPERVISOR_MODEL: str = "openai/gpt-oss-120b"
    OPENAI_API_KEY: str = "empty"
    OPENAI_COMPATIBLE_HOST: str = "http://localhost:11434"
    PREPROCESSING_MODEL: str = "openai/gpt-oss-20b"

    # Agent Card Configuration (Local JSON files for governance)
    GOOGLE_SEARCH_AGENT_CARD_FILE: str = "src/orchestrator/agent_cards/google_search_agent_card.json"
    GITHUB_AGENT_CARD_FILE: str = "src/orchestrator/agent_cards/github_agent_card.json"
    
    # Agent Base URLs (Optional - for syncing or fallback)
    GOOGLE_SEARCH_AGENT_MODEL: str = ""
    GITHUB_SEARCH_AGENT_MODEL: str = ""
    
    VERIFY_SSL: bool = False
    DEFAULT_TIMEOUT: int | None = None

    # Input Guardrails Configuration
    INPUT_GUARDRAILS_ENABLED: bool = True
    GUARDRAILS_MODEL: str = "openai/gpt-oss-120b"
    GUARDRAILS_CONFIDENCE_THRESHOLD: float = 0.7
    
    # Langfuse Tracing Configuration
    LANGFUSE_TRACING_ENABLED: bool = False
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_BASE_URL: str = "http://localhost:3000"

    @field_validator("VERIFY_SSL", mode="before")
    def convert_verify_ssl(cls, value):
        if isinstance(value, str):
            if value.lower() == "true":
                return True
            elif value.lower() == "false":
                return False
        return value

    class Config:
        case_sensitive = True
        extra = "allow"


app_cfg = ApiConfig(_env_file=".env")
