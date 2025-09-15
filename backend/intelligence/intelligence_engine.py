#!/usr/bin/env python3
"""
Intelligence Engine for Outstaffer Content Analysis
Processes segments using Firecrawl search and Gemini analysis
"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

# Import core pipeline components
from core.pipeline import ContentPipeline
from core.firecrawl_client import FirecrawlClient
from core.gemini_client import GeminiClient


class IntelligenceEngine:
    """Main intelligence engine for processing content segments"""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize with configuration"""
        self.config_path = config_path or "intelligence/config/intelligence_config.json"
        self.config = self._load_config()
        self.pipeline = ContentPipeline()
        self.run_id = datetime.now().strftime("%Y_%m_%d_%H%M")
        
    def _load_config(self) -> Dict[str, Any]:
        """Load intelligence configuration"""
        config_file = Path(self.config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Config file not found: {config_file}")
        
        with open(config_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _load_prompt(self, prompt_file: str) -> Optional[Dict[str, Any]]:
        """Load prompt configuration from JSON file"""
        prompt_path = Path("intelligence/config/prompts") / prompt_file
        if not prompt_path.exists():
            print(f"Warning: Prompt file not found: {prompt_path}")
            return None
        
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _log_progress(self, segment_name: str, action: str, details: Optional[str] = None):
        """Log processing progress"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {segment_name}: {action}")
        if details:
            print(f"          → {details}")
    
    def process_segment(self, segment_key: str, output_dir: Path) -> Dict[str, Any]:
        """Process a single segment with all its searches"""
        segment_config = self.config["segments"].get(segment_key)
        if not segment_config:
            return {"error": f"Segment {segment_key} not found in config"}
        
        segment_name = segment_config["name"]
        self._log_progress(segment_name, "Starting segment processing")
        
        # Load prompt configuration
        prompt_config = self._load_prompt(segment_config["prompt_file"])
        if not prompt_config:
            return {"error": f"Could not load prompt file: {segment_config['prompt_file']}"}
        
        # Create segment output directory
        segment_dir = output_dir / segment_key
        segment_dir.mkdir(parents=True, exist_ok=True)
        
        segment_results = {
            "segment_key": segment_key,
            "segment_name": segment_name,
            "started_at": datetime.now().isoformat(),
            "prompt_config": prompt_config,
            "search_results": [],
            "total_scraped": 0,
            "total_analyzed": 0
        }
        
        # Process each search in the segment
        searches = segment_config.get("searches", [])
        defaults = self.config.get("defaults", {})
        
        for i, search_config in enumerate(searches):
            search_query = search_config["query"]
            search_limit = search_config.get("limit", defaults.get("scrape_limit", 3))
            
            self._log_progress(segment_name, f"Search {i+1}/{len(searches)}", search_query)
            
            try:
                # Step 1: Search
                search_results = self.pipeline.search_only(search_query, search_limit * 2)
                
                if not search_results.get("results"):
                    segment_results["search_results"].append({
                        "query": search_query,
                        "status": "no_results",
                        "search_limit": search_limit
                    })
                    continue
                
                # Extract URLs (limit to configured amount)
                urls = []
                for item in search_results["results"][:search_limit]:
                    url = getattr(item, 'url', None) if hasattr(item, 'url') else item.get('url')
                    if url:
                        urls.append(url)
                
                # Step 2: Scrape URLs
                scrape_results = self.pipeline.scrape_urls(urls)
                successful_scrapes = [r for r in scrape_results if r.get('success', False)]
                
                # Step 3: Analyze content using segment-specific prompt
                analyses = []
                for scrape_result in successful_scrapes:
                    if scrape_result.get('markdown'):
                        # Use custom prompt from segment config
                        custom_prompt = prompt_config["user_prompt"].format(
                            content=scrape_result['markdown'][:8000]  # Limit content size
                        )
                        
                        analysis = self.pipeline.analyze_content(
                            scrape_result['markdown'], 
                            custom_prompt
                        )
                        analysis['source_url'] = scrape_result['url']
                        analysis['source_title'] = scrape_result.get('title', '')
                        analyses.append(analysis)
                
                successful_analyses = [a for a in analyses if a.get('success', False)]
                
                search_result = {
                    "query": search_query,
                    "status": "success",
                    "search_limit": search_limit,
                    "urls_found": len(search_results["results"]),
                    "urls_processed": len(urls),
                    "scraped_count": len(successful_scrapes),
                    "analyzed_count": len(successful_analyses),
                    "analyses": successful_analyses
                }
                
                segment_results["search_results"].append(search_result)
                segment_results["total_scraped"] += len(successful_scrapes)
                segment_results["total_analyzed"] += len(successful_analyses)
                
                self._log_progress(segment_name, f"Search {i+1} completed", 
                                 f"{len(successful_scrapes)} scraped, {len(successful_analyses)} analyzed")
                
            except Exception as e:
                self._log_progress(segment_name, f"Search {i+1} failed", str(e))
                segment_results["search_results"].append({
                    "query": search_query,
                    "status": "failed",
                    "error": str(e)
                })
        
        segment_results["completed_at"] = datetime.now().isoformat()
        
        # Save segment results
        results_file = segment_dir / f"{segment_key}_results_{self.run_id}.json"
        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump(segment_results, f, indent=2, ensure_ascii=False, default=str)
        
        self._log_progress(segment_name, "Segment completed", 
                          f"{segment_results['total_analyzed']} total analyses")
        
        return segment_results
    
    def run_all_segments(self) -> Dict[str, Any]:
        """Run all configured segments"""
        print(f"Starting Intelligence Engine - Run ID: {self.run_id}")
        print("=" * 60)
        
        # Create output directory
        output_dir = Path(f"intelligence_output_{self.run_id}")
        output_dir.mkdir(exist_ok=True)
        
        run_summary = {
            "run_id": self.run_id,
            "started_at": datetime.now().isoformat(),
            "config_defaults": self.config.get("defaults", {}),
            "segments": {}
        }
        
        # Process each segment
        for segment_key in self.config["segments"]:
            segment_results = self.process_segment(segment_key, output_dir)
            run_summary["segments"][segment_key] = segment_results
        
        run_summary["completed_at"] = datetime.now().isoformat()
        
        # Calculate totals
        total_analyzed = sum(s.get("total_analyzed", 0) for s in run_summary["segments"].values())
        total_scraped = sum(s.get("total_scraped", 0) for s in run_summary["segments"].values())
        total_searches = sum(len(s.get("search_results", [])) for s in run_summary["segments"].values())
        
        print("\n" + "=" * 60)
        print(f"Intelligence Run {self.run_id} Complete!")
        print(f"Segments processed: {len(run_summary['segments'])}")
        print(f"Total searches: {total_searches}")
        print(f"Total content scraped: {total_scraped}")
        print(f"Total AI analyses: {total_analyzed}")
        print(f"Output directory: {output_dir}")
        
        # Save run summary
        with open(output_dir / "run_summary.json", "w", encoding="utf-8") as f:
            json.dump(run_summary, f, indent=2, ensure_ascii=False, default=str)
        
        return run_summary
    
    def run_single_segment(self, segment_key: str) -> Dict[str, Any]:
        """Run a single segment"""
        print(f"Running segment: {segment_key}")
        
        output_dir = Path(f"intelligence_output_{self.run_id}")
        output_dir.mkdir(exist_ok=True)
        
        return self.process_segment(segment_key, output_dir)


def main():
    """Main entry point"""
    import sys
    
    try:
        engine = IntelligenceEngine()
        
        if len(sys.argv) > 1:
            # Run specific segment
            segment_key = sys.argv[1]
            if segment_key not in engine.config["segments"]:
                print(f"Error: Segment '{segment_key}' not found")
                print(f"Available segments: {list(engine.config['segments'].keys())}")
                return
            
            results = engine.run_single_segment(segment_key)
        else:
            # Run all segments
            results = engine.run_all_segments()
        
        print(f"\nResults saved to intelligence_output_{engine.run_id}/")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
