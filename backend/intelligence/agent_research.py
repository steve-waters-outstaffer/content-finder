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
        # (Initialization code remains the same...)
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

            # 2. Load the segment-specific details
            segment_file = f"planner_{segment_name.lower().replace(' ', '_')}.json"
            with open(config_dir / segment_file, 'r') as f:
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
            # Fallback to a generic prompt if a specific config doesn't exist
            print(f"Warning: No specific planner config found for '{segment_name}'. Using default.")
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

            # Clean the response - remove markdown code blocks
            response_text = resp.text.strip().replace('```json', '').replace('```', '').strip()

            queries = json.loads(response_text)
            if not isinstance(queries, list):
                raise ValueError("Planner did not return a list")

            return [q for q in queries if isinstance(q, str)][:max_queries]
        except Exception as e:
            print(f"Query planning failed: {e}")
            return [mission] # Fallback to original mission

    async def tavily_search(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """Search with Tavily API"""
        print(f"DEBUG: Starting Tavily search for: '{query}'")
        print(f"DEBUG: Tavily API key present: {bool(self.tavily_key and self.tavily_key != 'placeholder_key')}")
        
        payload = {
            "api_key": self.tavily_key,
            "query": query,
            "max_results": max_results,
            "search_depth": "advanced",
            "include_answer": True,
            "time_range": "year"  # Last 12 months
        }
        
        async with httpx.AsyncClient(timeout=60) as client:
            try:
                print(f"DEBUG: Making Tavily API request...")
                r = await client.post("https://api.tavily.com/search", json=payload)
                print(f"DEBUG: Tavily response status: {r.status_code}")
                r.raise_for_status()
                result = r.json()
                print(f"DEBUG: Tavily returned {len(result.get('results', []))} results")
                return result
            except Exception as e:
                print(f"DEBUG: Tavily search failed for '{query}': {e}")
                return {"results": []}

    async def scrape_url(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """Scrape a single URL with Firecrawl"""
        url = doc.get("url")
        if not url:
            return doc
        
        try:
            scrape_params = {'formats': ['markdown']}
            scraped_data = await self.firecrawl.scrape(url=url, params=scrape_params)
            
            if scraped_data.markdown:
                doc['passages'] = [scraped_data.markdown]
                print(f"  Scraped: {url}")
            else:
                print(f"  - No content: {url}")
        except Exception as e:
            print(f"  Scrape failed for {url}: {e}")
        
        return doc

    def dedupe_sources(self, search_batches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicate search results by URL"""
        seen, out = set(), []
        for batch in search_batches:
            for item in batch.get("results", []):
                url = item.get("url")
                if not url:
                    continue
                
                url_hash = hashlib.md5(url.encode()).hexdigest()
                if url_hash in seen:
                    continue
                
                seen.add(url_hash)
                out.append({
                    "title": (item.get("title") or "").strip(),
                    "url": url,
                    "domain": re.sub(r"^https?://(www\.)?([^/]+)/?.*$", r"\2", url),
                    "published_at": item.get("published_date") or item.get("published_time") or "",
                    "passages": [(item.get("content") or item.get("snippet") or "").strip()],
                })
        
        return out

    async def synthesize_insights(self, mission: str, segment_name: str, docs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Use Gemini to synthesize insights from scraped docs"""
        prompts = self.get_segment_prompts(segment_name)
        
        payload = {"mission": mission, "docs": docs[:100]}  # Limit for token constraints
        prompt_parts = [
            {"text": prompts['synthesis']},
            {"text": "Create insights based on these docs:"},
            {"text": "```json\n" + json.dumps(payload)[:300000] + "\n```"}
        ]
        
        try:
            resp = self.synthesizer.generate_content(prompt_parts)
            text = resp.text.strip()
            
            # Extract JSON from response
            import re
            json_match = re.search(r"\{(?:.|\n)*\}", text)
            if json_match:
                data = json.loads(json_match.group(0))
                return {
                    "content_themes": data.get("content_themes", []),
                    "brief_markdown": data.get("brief_markdown", "")
                }
        except Exception as e:
            print(f"Synthesis failed: {e}")
        
        return {
            "content_themes": [],
            "brief_markdown": "# Brief\n_Synthesis failed to parse._"
        }

    async def run_segment_research(self, segment_name: str, max_queries: int = 8, max_results_per_query: int = 5) -> Dict[str, Any]:
        """Run complete research pipeline for a segment"""
        
        # Generate mission based on segment
        if "smb" in segment_name.lower():
            mission = (
                "For SMB founders and hiring managers without recruiters: map current hiring trends, "
                "cost benchmarks, process efficiency tips, skills shortage solutions, and common mistakes. "
                "Focus on actionable insights for LinkedIn content. Last 12 months."
            )
        else:
            mission = f"Research current trends and insights for {segment_name} audience. Focus on actionable content for last 12 months."
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        result = {
            "segment_name": segment_name,
            "mission": mission,
            "timestamp": timestamp,
            "started_at": datetime.now().isoformat(),
            "queries": [],
            "sources": [],
            "content_themes": [],
            "brief_markdown": "",
            "status": "started"
        }
        
        try:
            # Step 1: Plan queries
            print(f"Planning queries for {segment_name}...")
            queries = await self.plan_queries(mission, segment_name, max_queries)
            result["queries"] = queries
            print(f"Generated {len(queries)} queries")
            
            # Step 2: Search with Tavily
            print(f"Searching with Tavily...")
            search_batches = []
            for query in queries:
                search_result = await self.tavily_search(query, max_results_per_query)
                search_batches.append(search_result)
                print(f"  Query: '{query}' -> {len(search_result.get('results', []))} results")
            
            # Step 3: Dedupe and scrape
            docs = self.dedupe_sources(search_batches)
            result["sources"] = docs
            print(f"Found {len(docs)} unique sources, scraping...")
            
            # Scrape content
            scrape_tasks = [self.scrape_url(doc) for doc in docs]
            scraped_docs = await asyncio.gather(*scrape_tasks)
            result["sources"] = scraped_docs
            
            successful_scrapes = len([d for d in scraped_docs if d.get('passages')])
            print(f"Successfully scraped {successful_scrapes}/{len(docs)} sources")
            
            # Step 4: Synthesize insights
            print(f"Synthesizing insights...")
            synthesis = await self.synthesize_insights(mission, segment_name, scraped_docs)
            result.update(synthesis)
            
            result["completed_at"] = datetime.now().isoformat()
            result["status"] = "completed"
            result["stats"] = {
                "queries_generated": len(queries),
                "sources_found": len(docs),
                "sources_scraped": successful_scrapes,
                "themes_generated": len(synthesis.get("content_themes", []))
            }
            
            print(f"Research completed for {segment_name}")
            return result
            
        except Exception as e:
            print(f"Research failed for {segment_name}: {e}")
            result["error"] = str(e)
            result["status"] = "failed"
            result["completed_at"] = datetime.now().isoformat()
            return result


# Usage example
async def main():
    researcher = AgentResearcher()
    result = await researcher.run_segment_research("SMB Leaders")
    print(json.dumps(result, indent=2, default=str))

if __name__ == "__main__":
    asyncio.run(main())
