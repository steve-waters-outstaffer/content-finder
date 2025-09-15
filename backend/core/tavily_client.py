"""Tavily API client wrapper for search operations"""
import os
from tavily import TavilyClient as Tavily

class TavilyApiClient:
    """Wrapper for Tavily search operations."""
    def __init__(self, api_key: str = None):
        if api_key is None:
            api_key = os.getenv("TAVILY_API_KEY")
        if not api_key:
            raise ValueError("Tavily API key not provided or set in TAVILY_API_KEY environment variable.")
        self.client = Tavily(api_key=api_key)

    def search(self, query: str, search_depth: str = "advanced", max_results: int = 7) -> list[dict]:
        """
        Performs a search using Tavily and returns a list of results.
        """
        try:
            response = self.client.search(
                query=query,
                search_depth=search_depth,
                max_results=max_results,
                include_domains=[],
                exclude_domains=[]
            )
            return response.get('results', [])
        except Exception as e:
            print(f"An error occurred during Tavily search: {e}")
            return []