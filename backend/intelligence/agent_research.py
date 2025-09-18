"""
Agent-based research engine for intelligence pipeline
Replaces static config searches with dynamic AI-generated queries
"""
import os
import json
import asyncio
import hashlib
import re
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

import httpx
import google.generativeai as genai
from firecrawl import AsyncFirecrawl

# Load environment variables
load_dotenv()

class AgentResearcher:
    """Agent-based research engine using Tavily + Firecrawl + Gemini"""

    def __init__(self):
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.tavily_key = os.getenv("TAVILY_API_KEY")
        self.firecrawl_key = os.getenv("FIRECRAWL_API_KEY")

        if not all([self.gemini_key, self.tavily_key, self.firecrawl_key]):
            raise RuntimeError("Missing required API keys: GEMINI_API_KEY, TAVILY_API_KEY, FIRECRAWL_API_KEY")

        genai.configure(api_key=self.gemini_key)
        self.firecrawl = AsyncFirecrawl(api_key=self.firecrawl_key)
        self.planner = genai.GenerativeModel("gemini-1.5-flash")
        self.synthesizer = genai.GenerativeModel("gemini-1.5-pro")

    def get_planner_prompt(self, segment_name: str) -> str:
        """Constructs the planner prompt from a base template and segment-specific config."""
        try:
            current_year = datetime.now().year
            config_dir = Path(__file__).parent / 'config' / 'prompts'

            # 1. Load the base template
            with open(config_dir / 'planner_base.txt', 'r') as f:
                base_template = f.read()

            # 2. Load the segment-specific details - CORRECTED FILENAME
            segment_file = f"segment_{segment_name.lower().replace(' ', '_')}.json"
            segment_config_path = config_dir / segment_file

            # Fallback to smb_leaders if a specific config doesn't exist
            if not segment_config_path.exists():
                print(f"Warning: No specific planner config found for '{segment_name}'. Falling back to smb_leaders config.")
                segment_config_path = config_dir / 'segment_smb_leaders.json'

            with open(segment_config_path, 'r') as f:
                segment_config = json.load(f)

            # 3. Format the lists from the config into bullet points
            priorities_str = "\n".join([f"- {item}" for item in segment_config.get("priorities", [])])
            focus_areas_str = "\n".join([f"- {item}" for item in segment_config.get("focus_areas", [])])

            # Inject current year into rules that need it
            rules_list = []
            for rule in segment_config.get("rules", []):
                formatted_rule = rule.format(
                    current_year=current_year,
                    past_year_1=current_year - 1,
                    past_year_2=current_year - 2
                )
                rules_list.append(f"- {formatted_rule}")
            rules_str = "\n".join(rules_list)

            # 4. Populate the template with the details
            prompt = base_template.format(
                current_year=current_year,
                audience=segment_config.get("audience", ""),
                priorities=priorities_str,
                focus_areas=focus_areas_str,
                rules=rules_str
            )
            return prompt

        except FileNotFoundError:
            # General fallback if no files can be found
            print(f"Warning: Could not find planner base or segment files. Using generic prompt.")
            return f"You are a research planner. The current year is {datetime.now().year}. Turn the mission into 8-12 web-ready search queries. Focus on recent data. Output a pure JSON array of strings."
        except Exception as e:
            print(f"Error loading planner prompt for {segment_name}: {e}")
            return f"You are a research planner. Turn the mission into 8-12 web-ready search queries."


    async def plan_queries(self, mission: str, segment_name: str, max_queries: int = 10) -> List[str]:
        """Use Gemini to generate focused queries for the mission"""
        planner_prompt = self.get_planner_prompt(segment_name)
        full_prompt = f"{planner_prompt}\n\nMission: {mission}\nReturn at most {max_queries} queries."

        try:
            resp = self.planner.generate_content(full_prompt)
            response_text = resp.text.strip().replace('```json', '').replace('```', '').strip()
            queries = json.loads(response_text)
            if not isinstance(queries, list):
                raise ValueError("Planner did not return a list")
            return [q for q in queries if isinstance(q, str)][:max_queries]
        except Exception as e:
            print(f"Query planning failed: {e}")
            return [mission]

    async def tavily_search(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """Search with Tavily API"""
        payload = {
            "api_key": self.tavily_key, "query": query, "max_results": max_results,
            "search_depth": "advanced", "include_answer": True
        }
        async with httpx.AsyncClient(timeout=60) as client:
            try:
                r = await client.post("https://api.tavily.com/search", json=payload)
                r.raise_for_status()
                return r.json()
            except Exception as e:
                print(f"Tavily search failed for '{query}': {e}")
                return {"results": []}

    async def scrape_url(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """Scrape a single URL with Firecrawl"""
        url = doc.get("url")
        if not url: return doc
        try:
            scraped_data = await self.firecrawl.scrape(url=url, params={'pageOptions': {'onlyMainContent': True}})
            if scraped_data and scraped_data.markdown:
                doc['passages'] = [scraped_data.markdown]
                print(f"  Scraped: {url}")
            else:
                doc['passages'] = [doc.get('content', '')] # Fallback to snippet
                print(f"  - No main content, using snippet: {url}")
        except Exception as e:
            print(f"  Scrape failed for {url}: {e}")
        return doc

    def dedupe_sources(self, search_batches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicate search results by URL"""
        seen, out = set(), []
        for batch in search_batches:
            for item in batch.get("results", []):
                url = item.get("url")
                if not url: continue
                if url in seen: continue
                seen.add(url)
                out.append(item)
        return out

    def get_segment_prompts(self, segment_name: str) -> Dict[str, str]:
        """Loads all relevant prompts for a given segment."""
        prompts = {}
        try:
            config_dir = Path(__file__).parent / 'config' / 'prompts'
            synthesis_prompt_path = config_dir / 'synthesis_prompt.txt'
            with open(synthesis_prompt_path, 'r') as f:
                prompts['synthesis'] = f.read()
            return prompts
        except FileNotFoundError as e:
            print(f"Error: Prompt file not found - {e}")
            return {'synthesis': "Analyze docs and generate content themes in JSON."}

    async def synthesize_insights(self, mission: str, segment_name: str, docs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Use Gemini to synthesize insights from scraped docs"""
        prompts = self.get_segment_prompts(segment_name)
        synthesis_template = prompts.get('synthesis')

        # Load segment description from the main config file
        try:
            config_path = Path(__file__).parent / 'config' / 'intelligence_config.json'
            with open(config_path, 'r') as f:
                full_config = json.load(f)
            segment_config = next((s for s in full_config.get("monthly_run", {}).get("segments", []) if s["name"] == segment_name), None)
            segment_description = segment_config.get("description", "No description provided.") if segment_config else "N/A"
        except Exception as e:
            print(f"Could not load segment description: {e}")
            segment_description = "N/A"

        combined_content = ""
        for doc in docs:
            content = (doc.get('passages') or [doc.get('content',' Snippet not available')])
            if content:
                combined_content += f"URL: {doc.get('url', 'N/A')}\\nTitle: {doc.get('title', 'N/A')}\\nContent Snippet:\\n{content[0][:2000]}\\n\\n---\\n\\n"

        final_prompt = synthesis_template.format(
            segment_name=segment_name,
            segment_description=segment_description,
            combined_content=combined_content
        )

        try:
            resp = self.synthesizer.generate_content(final_prompt)
            text = resp.text.strip()

            # Extract JSON array from the response
            json_match = re.search(r"\[\s*\{.*\}\s*\]", text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group(0))
                return {"content_themes": data}
            else:
                raise ValueError("Could not parse JSON array from synthesis response.")

        except Exception as e:
            print(f"Synthesis failed: {e}")
            return {"content_themes": []}

    async def run_segment_research(self, segment_name: str, max_queries: int = 8, max_results_per_query: int = 5) -> Dict[str, Any]:
        """Run complete research pipeline for a segment"""
        # Load the mission from the main config file
        try:
            config_path = Path(__file__).parent / 'config' / 'intelligence_config.json'
            with open(config_path, 'r') as f:
                full_config = json.load(f)
            segment_config = next((s for s in full_config.get("monthly_run", {}).get("segments", []) if s["name"] == segment_name), {})
            mission = segment_config.get("research_focus", f"Research current trends for {segment_name}.")
        except Exception as e:
            print(f"Could not load mission from config: {e}")
            mission = f"Research current trends and insights for {segment_name} audience."

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result = {
            "segment_name": segment_name, "mission": mission, "timestamp": timestamp,
            "started_at": datetime.now().isoformat(), "queries": [], "sources": [],
            "content_themes": [], "status": "started"
        }

        try:
            print(f"Planning queries for {segment_name}...")
            queries = await self.plan_queries(mission, segment_name, max_queries)
            result["queries"] = queries

            print(f"Searching with Tavily...")
            search_tasks = [self.tavily_search(q, max_results_per_query) for q in queries]
            search_batches = await asyncio.gather(*search_tasks)

            docs = self.dedupe_sources(search_batches)
            result["sources"] = docs
            print(f"Found {len(docs)} unique sources, scraping...")

            scrape_tasks = [self.scrape_url(doc) for doc in docs]
            scraped_docs = await asyncio.gather(*scrape_tasks)

            successful_scrapes = [d for d in scraped_docs if d.get('passages') and d['passages'][0]]
            print(f"Successfully scraped {len(successful_scrapes)}/{len(docs)} sources")

            if successful_scrapes:
                print(f"Synthesizing insights...")
                synthesis = await self.synthesize_insights(mission, segment_name, successful_scrapes)
                result.update(synthesis)

            result.update({
                "completed_at": datetime.now().isoformat(),
                "status": "completed",
                "stats": {
                    "queries_generated": len(queries), "sources_found": len(docs),
                    "sources_scraped": len(successful_scrapes), "themes_generated": len(result.get("content_themes", []))
                }
            })
            return result

        except Exception as e:
            result.update({"error": str(e), "status": "failed", "completed_at": datetime.now().isoformat()})
            return result