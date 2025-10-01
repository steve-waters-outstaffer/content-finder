"""
This module defines the AI agents used in the intelligence engine.
"""
from core.gemini_client import GeminiClient
from core.tavily_client import TavilyApiClient

class ResearchAgent:
    """An AI agent that uses search tools to find relevant URLs for a given topic."""

    def __init__(self, gemini_client: GeminiClient, tavily_client: TavilyApiClient):
        self.gemini_client = gemini_client
        self.tavily_client = tavily_client
        self.system_prompt = """
You are a world-class, expert research analyst. Your goal is to deeply understand a user's research objective
and use the provided search tool to find the most relevant, insightful, and high-quality URLs.

You will be given a research goal. Your process is as follows:
1.  **Deconstruct the Goal:** Break down the high-level goal into 3-5 specific, effective search queries that would be suitable for a web search engine.
2.  **Return Queries:** You MUST return these queries as a JSON object with a single key "queries" containing a list of strings. Do not return anything else. Example: {"queries": ["query 1", "query 2"]}
"""

    def plan_searches(self, research_goal: str) -> list[str]:
        """Uses an LLM to break a high-level goal into specific search queries."""
        print(f"🧠 Agent is planning searches for goal: {research_goal}")
        response_text = self.gemini_client.generate_text(
            prompt=research_goal,
            system_prompt=self.system_prompt
        )
        try:
            parsed = self.gemini_client.parse_json_response(response_text)
        except Exception as e:
            print(f"Error parsing agent's search plan: {e}")
            return []

        if isinstance(parsed, dict):
            queries = parsed.get("queries", [])
        else:
            queries = parsed

        return [str(item) for item in queries if isinstance(item, str)]

    def conduct_research(self, research_goal: str) -> list[dict]:
        """
        Conducts research based on a goal, plans queries, executes them,
        and returns a curated list of URLs.
        """
        search_queries = self.plan_searches(research_goal)
        if not search_queries:
            print(" Agent failed to generate a search plan.")
            return []

        all_results = []
        unique_urls = set()

        for query in search_queries:
            print(f"🔎 Agent is searching for: '{query}'")
            results = self.tavily_client.search(query)
            for result in results:
                if result.url not in unique_urls:
                    all_results.append({
                        "title": result.title or 'No Title',
                        "url": result.url,
                        "score": result.score,
                    })
                    unique_urls.add(result.url)

        # Sort results by score to prioritize relevance
        all_results.sort(key=lambda x: x['score'], reverse=True)

        print(f"✅ Agent research complete. Found {len(all_results)} unique URLs.")
        return all_results[:10] # Return top 10 results