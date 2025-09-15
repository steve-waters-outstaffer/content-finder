#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime
import subprocess
import sys

# Add parent directory to path to import agents and clients
sys.path.append(str(Path(__file__).resolve().parent.parent))

from core.gemini_client import GeminiClient
from core.tavily_client import TavilyApiClient
from intelligence.agents import ResearchAgent

class IntelligenceEngine:
    def __init__(self, config_path="backend/intelligence/config/intelligence_config.json"):
        self.config = self._load_json(config_path)
        self.gemini_client = GeminiClient()
        self.tavily_client = TavilyApiClient()
        self.research_agent = ResearchAgent(self.gemini_client, self.tavily_client)

        # Setup output directories
        self.month_str = datetime.now().strftime("%Y_%m")
        self.master_outdir = Path(f"intelligence_runs/{self.month_str}")
        self.master_outdir.mkdir(parents=True, exist_ok=True)

    def _load_json(self, path):
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Config file not found at {path}")
        return json.loads(p.read_text())

    def get_segments(self):
        """Returns the list of available segments from the config."""
        return self.config.get("monthly_run", {}).get("segments", [])

    def start_research_phase(self, segment_name: str) -> list[dict]:
        """
        Phase 1: Uses the research agent to find a list of URLs for a segment.
        """
        print(f"--- Starting Research Phase for Segment: {segment_name} ---")
        segment_config = next((s for s in self.get_segments() if s["name"] == segment_name), None)
        if not segment_config:
            raise ValueError(f"Segment '{segment_name}' not found in configuration.")

        research_goal = segment_config.get("research_goal")
        if not research_goal:
            raise ValueError(f"No 'research_goal' defined for segment '{segment_name}'.")

        # Delegate the complex research task to the agent
        research_results = self.research_agent.conduct_research(research_goal)

        # Save results for the next phase
        results_file = self.master_outdir / f"{segment_name.replace(' ', '_').lower()}_research_results.json"
        results_file.write_text(json.dumps(research_results, indent=2))
        print(f"Research results saved for review: {results_file}")

        return research_results

    def start_processing_phase(self, segment_name: str, urls_to_process: list[str]):
        """
        Phase 2: Scrapes and analyzes the user-approved list of URLs.
        """
        print(f"--- Starting Processing Phase for Segment: {segment_name} ---")
        segment_config = next((s for s in self.get_segments() if s["name"] == segment_name), None)
        if not segment_config:
            raise ValueError(f"Segment '{segment_name}' not found in configuration.")

        persona_prompt = segment_config.get("persona_prompt")
        segment_dir = self.master_outdir / segment_name.replace(" ", "_").lower()

        # Here you would call your existing Firecrawl scrape and Gemini analysis pipeline
        # For simplicity, we'll simulate this with print statements and subprocess calls
        print(f"Processing {len(urls_to_process)} URLs with persona: '{persona_prompt[:50]}...'")

        # Example of how you might integrate your existing content_pipeline.py
        # You would adapt content_pipeline.py to take a list of URLs and a prompt

        # For now, let's just log the plan
        processing_plan = {
            "segment": segment_name,
            "urls": urls_to_process,
            "output_dir": str(segment_dir)
        }
        plan_file = segment_dir / "processing_plan.json"
        plan_file.parent.mkdir(parents=True, exist_ok=True)
        plan_file.write_text(json.dumps(processing_plan, indent=2))

        print(f"✅ Processing plan saved to {plan_file}. The next step would be to scrape and analyze.")
        # In a real implementation, you would now loop through the URLs,
        # call firecrawl_client.scrape(), and then gemini_client.analyze().