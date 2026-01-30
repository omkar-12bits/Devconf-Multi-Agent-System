import json
import logging
import os

from tavily import TavilyClient
from google.adk.tools import FunctionTool

logger = logging.getLogger(__name__)

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
if not TAVILY_API_KEY:
    logger.error("TAVILY_API_KEY environment variable is not set")
    raise ValueError("TAVILY_API_KEY environment variable is not set")

tavily_client = TavilyClient(api_key=TAVILY_API_KEY)


def search_web(query: str, max_results: int = 5, search_depth: str = "basic") -> str:
    """Search the web for information.
    Args:
        query: The search query to search the web.
        max_results: The maximum number of results to return.
        search_depth: The depth of the search.
            "basic": Basic search (default).
            "advanced": Advanced search.
    Returns:
        A JSON object with the search results or an error message if the search fails.
    """
    if not tavily_client:
        logger.error("Tavily client not initialized")
        return json.dumps({
            "error": "Tavily API key not configured. Set TAVILY_API_KEY environment variable."
        })
    try:
        response = tavily_client.search(
            query=query,
            max_results=max_results,
            search_depth=search_depth
        )
        search_results = {
                "query": query,
                "results": []
            }
            
        for result in response.get("results", []):
            search_results["results"].append({
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "content": result.get("content", ""),
                "published_date": result.get("published_date", ""),
                "score": result.get("score", 0)
            })

        return json.dumps(search_results, indent=2)
    except Exception as e:
        logger.error(f"Error searching the web: {e}")
        return json.dumps({
            "error": f"Error searching the web: {e}"
        })

search_web_tool = FunctionTool(func=search_web)