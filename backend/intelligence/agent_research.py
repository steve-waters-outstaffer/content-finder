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
        print(f"DEBUG: Initializing AgentResearcher...")
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.tavily_key = os.getenv("TAVILY_API_KEY") 
        self.firecrawl_key = os.getenv("FIRECRAWL_API_KEY")
        
        print(f"DEBUG: API Keys loaded - Gemini: {bool(self.gemini_key)}, Tavily: {bool(self.tavily_key)}, Firecrawl: {bool(self.firecrawl_key)}")
        print(f"DEBUG: Gemini key starts with: {self.gemini_key[:10] if self.gemini_key else 'None'}...")
        print(f"DEBUG: Tavily key starts with: {self.tavily_key[:10] if self.tavily_key else 'None'}...")
        print(f"DEBUG: Firecrawl key starts with: {self.firecrawl_key[:10] if self.firecrawl_key else 'None'}...")
        
        if not all([self.gemini_key, self.tavily_key, self.firecrawl_key]):
            raise RuntimeError("Missing required API keys: GEMINI_API_KEY, TAVILY_API_KEY, FIRECRAWL_API_KEY")
        
        print(f"DEBUG: Configuring Gemini...")
        genai.configure(api_key=self.gemini_key)
        print(f"DEBUG: Initializing Firecrawl...")
        self.firecrawl = AsyncFirecrawl(api_key=self.firecrawl_key)
        print(f"DEBUG: Creating Gemini models...")
        self.planner = genai.GenerativeModel("gemini-1.5-flash")
        self.synthesizer = genai.GenerativeModel("gemini-1.5-pro")
        print(f"DEBUG: AgentResearcher initialized successfully")
    
    def get_segment_prompts(self, segment_name: str) -> Dict[str, str]:
        """Get planner and synthesis prompts based on segment"""
        
        if "smb" in segment_name.lower() or "leaders" in segment_name.lower():
            return {
                "planner": """You are a research planner for LinkedIn content creation.
Turn ONE mission into 8-12 crisp, web-ready queries.

Audience: Founders, COOs, and Hiring Managers at growing SMBs with no in-house recruiter.

Prioritise:
- SMB hiring challenges and solutions
- Recruitment pain points and frustrations  
- Talent acquisition trends for growing companies
- Cost-effective hiring strategies
- Time-to-fill and process efficiency
- Skills shortages and market insights
- Founder-led recruiting realities

Focus Areas:
- LinkedIn Talent Solutions data and insights
- Strategic workforce planning trends (Gartner, McKinsey, Deloitte)
- Salary benchmarks and recruitment costs (Statista)
- Real practitioner pain points (Reddit r/recruitinghell, r/humanresources, r/startups)
- Common hiring questions and confusions (Quora)
- Interview process feedback (Glassdoor, Indeed reviews)

Rules:
- Target content that would resonate with SMB leaders doing their own recruiting
- Look for data, trends, and insights that make compelling LinkedIn posts
- Prefer recent data (last 12 months) for relevance
- Output a pure JSON array of strings (queries). No extra text.""",

                "synthesis": """You synthesise insights for LinkedIn content targeting SMB hiring leaders.
Given docs[] (title, url, passages[], published_at, domain), produce:
- 5-8 CONTENT THEMES perfect for LinkedIn posts
- For each theme: key insight, supporting data/metrics, why SMBs should care, 1-2 compelling quotes with citations [n]
- Focus on actionable, shareable insights that founders/COOs would engage with

Target Audience: Founders, COOs, and Hiring Managers at growing SMBs without in-house recruiters.

Content Themes Should Cover:
- Hiring process efficiency and speed
- Cost-effective recruitment strategies  
- Skills shortage solutions
- Market salary benchmarks and trends
- Common hiring mistakes to avoid
- Technology and tools for SMB recruiting
- Workforce planning for growth
- Competitor hiring insights

Constraints:
- Only cite URLs we actually saw in docs
- Prioritise data and metrics that make compelling LinkedIn posts
- Focus on pain points SMB leaders actually face
- Keep insights practical and immediately actionable

Output JSON with keys:
{
  "content_themes": [
    { 
      "theme": "", 
      "key_insight": "", 
      "supporting_data": [], 
      "why_smbs_care": "", 
      "linkedin_angle": "",
      "evidence": [ { "quote": "", "url": "" } ] 
    }
  ],
  "brief_markdown": "## LinkedIn Content Brief\\n"
}"""
            }
        
        # Default prompts for other segments
        return {
            "planner": """You are a research planner for content creation.
Turn ONE mission into 8-12 crisp, web-ready queries for your target audience.

Rules:
- Make queries specific and web-searchable
- Focus on recent trends and data (last 12 months)
- Target pain points and actionable insights
- Output a pure JSON array of strings (queries). No extra text.""",

            "synthesis": """You synthesise insights for content creation.
Given docs[] (title, url, passages[], published_at, domain), produce actionable insights.

Output JSON with keys:
{
  "content_themes": [
    { 
      "theme": "", 
      "key_insight": "", 
      "supporting_data": [], 
      "evidence": [ { "quote": "", "url": "" } ] 
    }
  ],
  "brief_markdown": "## Content Brief\\n"
}"""
        }

    async def plan_queries(self, mission: str, segment_name: str, max_queries: int = 10) -> List[str]:
        """Use Gemini to generate focused queries for the mission"""
        print(f"DEBUG: Planning queries for mission: '{mission}'")
        print(f"DEBUG: Gemini API key present: {bool(self.gemini_key and self.gemini_key != 'placeholder_key')}")
        
        prompts = self.get_segment_prompts(segment_name)
        prompt = f"{prompts['planner']}\n\nMission: {mission}\nReturn at most {max_queries} queries."
        
        try:
            print(f"DEBUG: Calling Gemini for query planning...")
            resp = self.planner.generate_content(prompt)
            print(f"DEBUG: Gemini response received, parsing JSON...")
            print(f"DEBUG: Raw Gemini response: {resp.text[:200]}...")
            
            # Clean the response - remove markdown code blocks if present
            response_text = resp.text.strip()
            if response_text.startswith('```json'):
                response_text = response_text[7:]  # Remove ```json
            if response_text.startswith('```'):
                response_text = response_text[3:]   # Remove ```
            if response_text.endswith('```'):
                response_text = response_text[:-3]  # Remove trailing ```
            response_text = response_text.strip()
            
            print(f"DEBUG: Cleaned response: {response_text[:200]}...")
            
            queries = json.loads(response_text)
            if not isinstance(queries, list):
                raise ValueError("Planner did not return a list")
            
            filtered_queries = [q for q in queries if isinstance(q, str)][:max_queries]
            print(f"DEBUG: Successfully parsed {len(filtered_queries)} queries")
            return filtered_queries
        except Exception as e:
            print(f"DEBUG: Query planning failed: {e}")
            print(f"DEBUG: Falling back to original mission as query")
            return [mission]  # Fallback to original mission

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
