"""Agent-based research workflow for the intelligence pipeline."""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from dotenv import load_dotenv

from core.firecrawl_client import AsyncFirecrawlClient, ScrapeResult
from core.gemini_client import GeminiClient, GeminiClientError
from core.tavily_client import TavilyApiClient, TavilyClientError, TavilyResult

# Load environment variables when running locally/scripts
load_dotenv()


@dataclass(slots=True)
class ResearchSource:
    """Minimal representation of a researched source."""

    title: str
    url: str
    snippet: str
    score: float

    @classmethod
    def from_tavily(cls, result: TavilyResult) -> "ResearchSource":
        return cls(
            title=result.title,
            url=result.url,
            snippet=result.snippet,
            score=result.score,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "score": self.score,
        }


class AgentResearcher:
    """Agent-based research engine using Tavily + Firecrawl + Gemini."""

    def __init__(
        self,
        *,
        gemini_client: Optional[GeminiClient] = None,
        tavily_client: Optional[TavilyApiClient] = None,
        firecrawl_client: Optional[AsyncFirecrawlClient] = None,
        prompts_dir: Optional[Path | str] = None,
    ) -> None:
        self.gemini = gemini_client or GeminiClient()
        self.tavily = tavily_client or TavilyApiClient()
        self.firecrawl = firecrawl_client or AsyncFirecrawlClient()

        self.prompts_dir = Path(
            prompts_dir or Path(__file__).parent / "config" / "prompts"
        )
        self.flash_model = self.gemini.default_model
        self.pro_model = os.environ.get("MODEL_PRO", self.flash_model)

    # ------------------------------------------------------------------
    # Prompt helpers
    # ------------------------------------------------------------------
    def _load_prompt(self, filename: str) -> str:
        path = self.prompts_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"Prompt template not found: {path}")
        return path.read_text(encoding="utf-8")

    def _load_intelligence_config(self) -> Dict[str, Any]:
        config_path = Path(__file__).parent / "config" / "intelligence_config.json"
        if not config_path.exists():
            return {}
        try:
            return json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _get_segment_config(self, segment_name: str) -> Dict[str, Any]:
        config = self._load_intelligence_config()
        segments = config.get("monthly_run", {}).get("segments", [])
        return next((s for s in segments if s.get("name") == segment_name), {})

    def get_planner_prompt(self, segment_name: str) -> str:
        """Construct the planner prompt from base + segment configuration."""

        current_year = datetime.now().year
        config_dir = self.prompts_dir

        try:
            base_template = self._load_prompt("planner_base.txt")
        except FileNotFoundError:
            return (
                "You are a research planner. Return a JSON array of useful web "
                "search queries for the given mission."
            )

        segment_slug = segment_name.lower().replace(" ", "_")
        segment_file = config_dir / f"segment_{segment_slug}.json"
        if not segment_file.exists():
            segment_file = config_dir / "segment_smb_leaders.json"

        try:
            segment_config = json.loads(segment_file.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            segment_config = {}

        priorities = "\n".join(f"- {item}" for item in segment_config.get("priorities", []))
        focus_areas = "\n".join(f"- {item}" for item in segment_config.get("focus_areas", []))

        formatted_rules: List[str] = []
        for rule in segment_config.get("rules", []):
            formatted_rules.append(
                f"- {rule.format(current_year=current_year, past_year_1=current_year - 1, past_year_2=current_year - 2)}"
            )

        return base_template.format(
            current_year=current_year,
            audience=segment_config.get("audience", ""),
            priorities=priorities,
            focus_areas=focus_areas,
            rules="\n".join(formatted_rules),
        )

    # ------------------------------------------------------------------
    # Core research workflow
    # ------------------------------------------------------------------
    async def plan_queries(self, mission: str, segment_name: str, max_queries: int = 10) -> List[str]:
        planner_context = self.get_planner_prompt(segment_name)

        try:
            response = self.gemini.generate_json_response(
                "agent_research_planner_prompt.txt",
                {
                    "planner_context": planner_context,
                    "mission": mission,
                    "max_queries": max_queries,
                },
                model=self.flash_model,
                temperature=0.3,
                max_output_tokens=1024,
            )
        except GeminiClientError as exc:
            print(f"Query planning failed: {exc}")
            return [mission]

        payload = response.data
        if isinstance(payload, dict):
            candidates = payload.get("queries")
        else:
            candidates = payload

        queries: List[str] = []
        for item in candidates or []:
            if isinstance(item, str) and item.strip():
                queries.append(item.strip())
        return queries[:max_queries] or [mission]

    async def tavily_search(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        try:
            results = await asyncio.to_thread(
                self.tavily.search,
                query,
                max_results=max_results,
            )
        except TavilyClientError as exc:
            print(f"Tavily search failed for '{query}': {exc}")
            return {"results": []}

        return {"results": [ResearchSource.from_tavily(r).to_dict() for r in results]}

    async def scrape_url(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        url = doc.get("url")
        if not url:
            return doc

        scrape_result: ScrapeResult = await self.firecrawl.scrape(url=url)
        if scrape_result.success and scrape_result.markdown:
            doc["passages"] = [scrape_result.markdown]
        else:
            doc["passages"] = [doc.get("snippet") or doc.get("content") or ""]
            if scrape_result.error:
                doc["scrape_error"] = scrape_result.error
        return doc

    def dedupe_sources(self, search_batches: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen: set[str] = set()
        deduped: List[Dict[str, Any]] = []
        for batch in search_batches:
            for item in batch.get("results", []):
                url = item.get("url") if isinstance(item, dict) else None
                if not url or url in seen:
                    continue
                seen.add(url)
                deduped.append(item)
        return deduped

    def synthesize_insights(self, mission: str, segment_name: str, docs: List[Dict[str, Any]]) -> Dict[str, Any]:
        template_name = "synthesis_prompt.txt"
        if not (self.prompts_dir / template_name).exists():
            print("Synthesis prompt template missing; skipping insight generation.")
            return {"content_themes": []}

        segment_config = self._get_segment_config(segment_name)
        segment_description = segment_config.get("description", "")

        combined_chunks = []
        for doc in docs:
            body = (doc.get("passages") or [doc.get("snippet") or ""])[0]
            combined_chunks.append(
                f"URL: {doc.get('url', 'N/A')}\nTitle: {doc.get('title', 'N/A')}\nContent Snippet:\n{body[:2000]}\n\n---\n"
            )

        prompt_context = {
            "segment_name": segment_name,
            "segment_description": segment_description,
            "combined_content": "\n".join(combined_chunks),
        }

        try:
            response = self.gemini.generate_json_response(
                template_name,
                prompt_context,
                model=self.pro_model,
                temperature=0.4,
                max_output_tokens=2048,
            )
        except GeminiClientError as exc:
            print(f"Synthesis failed: {exc}")
            return {"content_themes": []}

        data = response.data
        if isinstance(data, list):
            return {"content_themes": data}
        return {"content_themes": []}

    async def run_segment_research(
        self,
        segment_name: str,
        *,
        max_queries: int = 8,
        max_results_per_query: int = 5,
    ) -> Dict[str, Any]:
        segment_config = self._get_segment_config(segment_name)
        mission = segment_config.get(
            "research_focus",
            f"Research current trends and insights for {segment_name}.",
        )

        timestamp = datetime.utcnow().isoformat()
        result: Dict[str, Any] = {
            "segment_name": segment_name,
            "mission": mission,
            "timestamp": timestamp,
            "status": "started",
            "queries": [],
            "sources": [],
            "content_themes": [],
        }

        try:
            queries = await self.plan_queries(mission, segment_name, max_queries)
            result["queries"] = queries

            search_tasks = [self.tavily_search(query, max_results_per_query) for query in queries]
            search_batches = await asyncio.gather(*search_tasks)
            deduped_sources = self.dedupe_sources(search_batches)
            result["sources"] = deduped_sources

            scrape_tasks = [self.scrape_url(dict(source)) for source in deduped_sources]
            scraped_docs = await asyncio.gather(*scrape_tasks)
            successful = [doc for doc in scraped_docs if doc.get("passages") and doc["passages"][0]]

            if successful:
                synthesis = self.synthesize_insights(mission, segment_name, successful)
                result.update(synthesis)

            result["status"] = "completed"
            result["completed_at"] = datetime.utcnow().isoformat()
            result["stats"] = {
                "queries_generated": len(queries),
                "sources_found": len(deduped_sources),
                "sources_scraped": len(successful),
                "themes_generated": len(result.get("content_themes", [])),
            }
            return result
        except Exception as exc:  # noqa: BLE001
            result["status"] = "failed"
            result["error"] = str(exc)
            result["completed_at"] = datetime.utcnow().isoformat()
            return result

