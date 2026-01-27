from enum import Enum


DEFAULT_LANGUAGE = "English"


class AgentNames(str, Enum):
    PREPROCESS_AGENT = "preprocess_agent"
    QUERY_FORWARDER_AGENT = "query_forwarder"
    ROUTING_AGENT = "routing_agent"
    POSTPROCESS_AGENT = "post_process_agent"
    SUPERVISOR_AGENT = "supervisor_workflow"
    WEB_SEARCH_AGENT = "web_search_agent"
    GITHUB_AGENT = "github_agent"


# Agent names to collect responses from (used in response extraction)
RESPONSE_COLLECTION_AGENTS = [
    AgentNames.ROUTING_AGENT.value,
    AgentNames.WEB_SEARCH_AGENT.value,
    AgentNames.GITHUB_AGENT.value,
]

