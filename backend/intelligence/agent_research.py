"""Agent-based research workflow for the intelligence pipeline."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional

from dotenv import load_dotenv

from core.firecrawl_client import AsyncFirecrawlClient, ScrapeResult
from core.gemini_client import GeminiClient, GeminiClientError
from core.tavily_client import TavilyApiClient, TavilyClientError, TavilyResult
from intelligence.models import MultiArticleAnalysis, QueryPlan, SynthesisResult

logger = logging.getLogger(__name__)

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
        start_time = time.perf_counter()
        self.gemini = gemini_client or GeminiClient()
        self.tavily = tavily_client or TavilyApiClient()
        self.firecrawl = firecrawl_client or AsyncFirecrawlClient()

        self.prompts_dir = Path(
            prompts_dir or Path(__file__).parent / "config" / "prompts"
        )
        self.flash_model = self.gemini.default_model
        self.pro_model = os.environ.get("MODEL_PRO", self.flash_model)
        logger.info(
            "AgentResearcher initialized",
            extra={
                "operation": "agent_init",
                "duration_ms": round((time.perf_counter() - start_time) * 1000, 2),
            },
        )

    # ------------------------------------------------------------------
    # Prompt helpers
    # ------------------------------------------------------------------
    def _load_prompt(self, filename: str) -> str:
        path = self.prompts_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"Prompt template not found: {path}")
        logger.debug(
            "Prompt loaded",
            extra={
                "operation": "prompt_load",
                "prompt": filename,
            },
        )
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
    async def plan_queries(
        self,
        mission: str,
        segment_name: str,
        max_queries: int = 10,
        log_callback: Optional[Callable[[str, str], None]] = None,
    ) -> List[str]:
        planner_context = self.get_planner_prompt(segment_name)

        logger.info(
            "Planning queries",
            extra={
                "operation": "agent_plan_queries",
                "segment_name": segment_name,
                "mission": mission,
                "max_queries": max_queries,
            },
        )

        logger.debug(
            "Planner prompt context assembled for Gemini.",
            extra={
                "operation": "agent_plan_queries",
                "segment_name": segment_name,
                "planner_context": planner_context,
            },
        )
        if log_callback:
            log_callback(
                f"Planner prompt context assembled for Gemini.\n{planner_context}",
                "debug",
            )

        try:
            start_time = time.perf_counter()
            logger.info(
                "Sending query generation request to Gemini with model %s.",
                self.flash_model,
                extra={
                    "operation": "agent_plan_queries",
                    "segment_name": segment_name,
                    "model": self.flash_model,
                },
            )
            if log_callback:
                log_callback(
                    f"Sending query generation request to Gemini with model {self.flash_model}.",
                    "info",
                )

            response = self.gemini.generate_structured_response(
                "agent_research_planner_prompt.txt",
                {
                    "planner_context": planner_context,
                    "mission": mission,
                    "max_queries": max_queries,
                },
                response_model=QueryPlan,
                model=self.flash_model,
                temperature=0.3,
                max_output_tokens=1024,
            )
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.info(
                "Received response from Gemini for query planning.",
                extra={
                    "operation": "agent_plan_queries",
                    "segment_name": segment_name,
                    "duration_ms": duration_ms,
                },
            )
            if log_callback:
                log_callback("Received response from Gemini for query planning.", "info")
        except GeminiClientError as exc:
            logger.exception(
                "Query planning failed",
                extra={
                    "operation": "agent_plan_queries",
                    "segment_name": segment_name,
                    "mission": mission,
                },
            )
            if log_callback:
                log_callback(f"Gemini query planning failed: {exc}", "error")
            return [mission]

        final_queries = [
            item.query.strip()
            for item in response.queries
            if isinstance(item.query, str) and item.query.strip()
        ]
        logger.info(
            "Successfully parsed %s queries from Gemini response.",
            len(final_queries),
            extra={
                "operation": "agent_plan_queries",
                "segment_name": segment_name,
                "duration_ms": locals().get("duration_ms"),
            },
        )
        if log_callback:
            log_callback(
                f"Successfully parsed {len(final_queries)} queries from Gemini response.",
                "info",
            )

        logger.info(
            "Query planning completed",
            extra={
                "operation": "agent_plan_queries",
                "segment_name": segment_name,
                "count": len(final_queries[:max_queries] or [mission]),
                "duration_ms": locals().get("duration_ms"),
            },
        )
        return final_queries[:max_queries] or [mission]

    async def tavily_search(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        logger.debug(
            "Executing Tavily search",
            extra={
                "operation": "tavily_search",
                "query": query,
                "max_results": max_results,
            },
        )
        try:
            start_time = time.perf_counter()
            results = await asyncio.to_thread(
                self.tavily.search,
                query,
                max_results=max_results,
            )
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.info(
                "Tavily search completed",
                extra={
                    "operation": "tavily_search",
                    "query": query,
                    "result_count": len(results),
                    "duration_ms": duration_ms,
                },
            )
        except TavilyClientError as exc:
            logger.error(
                "Tavily search failed",
                exc_info=exc,
                extra={
                    "operation": "tavily_search",
                    "query": query,
                },
            )
            return {"results": []}

        return {"results": [ResearchSource.from_tavily(r).to_dict() for r in results]}

    async def scrape_url(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        url = doc.get("url")
        if not url:
            logger.warning(
                "Document missing URL for scraping",
                extra={"operation": "firecrawl_scrape"},
            )
            return doc

        logger.debug(
            "Scraping URL",
            extra={
                "operation": "firecrawl_scrape",
                "url": url,
            },
        )
        scrape_start = time.perf_counter()
        scrape_result: ScrapeResult = await self.firecrawl.scrape(url=url)
        duration_ms = round((time.perf_counter() - scrape_start) * 1000, 2)
        if scrape_result.success and scrape_result.markdown:
            doc["passages"] = [scrape_result.markdown]
            logger.info(
                "Scrape succeeded",
                extra={
                    "operation": "firecrawl_scrape",
                    "url": url,
                    "duration_ms": duration_ms,
                },
            )
        else:
            doc["passages"] = [doc.get("snippet") or doc.get("content") or ""]
            if scrape_result.error:
                doc["scrape_error"] = scrape_result.error
                logger.warning(
                    "Scrape returned fallback content",
                    extra={
                        "operation": "firecrawl_scrape",
                        "url": url,
                        "duration_ms": duration_ms,
                        "error": scrape_result.error,
                    },
                )
        return doc

    def dedupe_sources(self, search_batches: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        seen: set[str] = set()
        deduped: List[Dict[str, Any]] = []
        logger.debug(
            "Deduping sources",
            extra={"operation": "agent_dedupe"},
        )
        for batch in search_batches:
            for item in batch.get("results", []):
                url = item.get("url") if isinstance(item, dict) else None
                if not url or url in seen:
                    continue
                seen.add(url)
                deduped.append(item)
        logger.info(
            "Deduping complete",
            extra={
                "operation": "agent_dedupe",
                "count": len(deduped),
            },
        )
        return deduped

    def synthesize_insights(
        self,
        mission: str,
        segment_name: str,
        docs: List[Dict[str, Any]],
        log_callback: Optional[Callable[[str, str], None]] = None,
        *,
        quick_research: bool = False,
    ) -> Dict[str, Any] | MultiArticleAnalysis:
        template_name = "multi_article_analysis_prompt.txt" if quick_research else "synthesis_prompt.txt"
        if not (self.prompts_dir / template_name).exists():
            logger.warning(
                "Synthesis prompt template missing; skipping insight generation.",
                extra={"operation": "agent_synthesis", "segment_name": segment_name},
            )
            if quick_research:
                raise GeminiClientError("Synthesis prompt template missing for quick research.")
            return {"content_themes": []}

        segment_config = self._get_segment_config(segment_name)
        segment_description = segment_config.get("description", "")

        logger.info(
            "Combining content from %s scraped documents for synthesis.",
            len(docs),
            extra={
                "operation": "agent_synthesis",
                "segment_name": segment_name,
                "doc_count": len(docs),
            },
        )
        if log_callback:
            log_callback(
                f"Combining content from {len(docs)} scraped documents for synthesis.",
                "info",
            )

        combined_chunks = []
        for doc in docs:
            body = (doc.get("passages") or [doc.get("snippet") or ""])[0]
            combined_chunks.append(
                f"URL: {doc.get('url', 'N/A')}\nTitle: {doc.get('title', 'N/A')}\nContent Snippet:\n{body[:2000]}\n\n---\n"
            )

        if quick_research:
            prompt_context: Dict[str, Any] = {
                "combined_content": "\n".join(combined_chunks),
            }
        else:
            prompt_context = {
                "segment_name": segment_name,
                "segment_description": segment_description,
                "combined_content": "\n".join(combined_chunks),
            }

        logger.info(
            "Generating synthesis",
            extra={
                "operation": "agent_synthesis",
                "segment_name": segment_name,
                "doc_count": len(docs),
            },
        )
        if log_callback:
            log_callback(
                f"Sending synthesis request to Gemini with model {self.pro_model}.",
                "info",
            )
        try:
            start_time = time.perf_counter()
            logger.info(
                "Sending synthesis request to Gemini with model %s.",
                self.pro_model,
                extra={
                    "operation": "agent_synthesis",
                    "segment_name": segment_name,
                    "model": self.pro_model,
                },
            )
            response = self.gemini.generate_structured_response(
                template_name,
                prompt_context,
                response_model=MultiArticleAnalysis if quick_research else SynthesisResult,
                model=self.pro_model,
                temperature=0.4,
                max_output_tokens=2048,
            )
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.info(
                "Received response from Gemini for synthesis.",
                extra={
                    "operation": "agent_synthesis",
                    "segment_name": segment_name,
                    "duration_ms": duration_ms,
                },
            )
            if log_callback:
                log_callback("Received response from Gemini for synthesis.", "info")
        except GeminiClientError as exc:
            logger.exception(
                "Synthesis failed",
                extra={
                    "operation": "agent_synthesis",
                    "segment_name": segment_name,
                },
            )
            if log_callback:
                log_callback(f"Gemini synthesis failed: {exc}", "error")
            if quick_research:
                raise
            return {"content_themes": []}

        if quick_research:
            return response

        themes = [theme.model_dump() for theme in response.content_themes]
        logger.info(
            "Synthesis completed",
            extra={
                "operation": "agent_synthesis",
                "segment_name": segment_name,
                "themes_generated": len(themes),
                "duration_ms": duration_ms,
            },
        )
        if log_callback:
            log_callback(
                f"Synthesis completed with {len(themes)} themes generated.",
                "info",
            )
        return {"content_themes": themes}

    async def run_segment_research(
        self,
        segment_name: str,
        *,
        max_queries: int = 8,
        max_results_per_query: int = 5,
    ) -> Dict[str, Any]:
        logger.info(
            "Starting agent research workflow",
            extra={
                "operation": "agent_run_segment",
                "segment_name": segment_name,
                "max_queries": max_queries,
                "max_results_per_query": max_results_per_query,
            },
        )
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

        workflow_start = time.perf_counter()
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
            logger.info(
                "Agent research workflow completed",
                extra={
                    "operation": "agent_run_segment",
                    "segment_name": segment_name,
                    "duration_ms": round((time.perf_counter() - workflow_start) * 1000, 2),
                    "stats": result["stats"],
                },
            )
            return result
        except Exception as exc:  # noqa: BLE001
            result["status"] = "failed"
            result["error"] = str(exc)
            result["completed_at"] = datetime.utcnow().isoformat()
            logger.exception(
                "Agent research workflow failed",
                extra={
                    "operation": "agent_run_segment",
                    "segment_name": segment_name,
                },
            )
            return result

