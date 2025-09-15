#!/usr/bin/env python3
"""
Enhanced Firecrawl search for intelligence gathering.
Uses Firecrawl's advanced search parameters for targeted content discovery.
"""
import os
import json
import requests
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

class IntelligenceFirecrawlSearch:
    def __init__(self):
        self.api_key = os.getenv('FIRECRAWL_API_KEY')
        if not self.api_key:
            raise ValueError("FIRECRAWL_API_KEY environment variable not set")
        
        self.base_url = "https://api.firecrawl.dev/v2"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    def enhanced_search(self, search_config: Dict, limit: int = 10, scrape_content: bool = True) -> Dict:
        """
        Perform enhanced search using Firecrawl with advanced parameters.
        
        Args:
            search_config: Dictionary containing query, sources, tbs, location, categories
            limit: Maximum number of results to return
            scrape_content: Whether to scrape content from results
        
        Returns:
            Dictionary containing search results and scraped content
        """
        # Build the search payload
        payload = {
            "query": search_config["query"],
            "limit": limit
        }
        
        # Add optional parameters if present
        if "sources" in search_config:
            payload["sources"] = [{"type": source} for source in search_config["sources"]]
        
        if "tbs" in search_config:
            payload["tbs"] = search_config["tbs"]
        
        if "location" in search_config:
            payload["location"] = search_config["location"]
        
        if "categories" in search_config:
            payload["categories"] = [{"type": cat} for cat in search_config["categories"]]
        
        # Add scraping options if requested
        if scrape_content:
            payload["scrapeOptions"] = {
                "formats": ["markdown", "links"],
                "onlyMainContent": True,
                "maxAge": 2592000000,  # 30 days cache
                "timeout": 30000,
                "removeBase64Images": True,
                "blockAds": True
            }
        
        try:
            print(f"Searching: {search_config['query']}")
            response = requests.post(
                f"{self.base_url}/search",
                headers=self.headers,
                json=payload,
                timeout=60
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    return self._process_search_results(data.get("data", {}), search_config)
                else:
                    return {"error": f"Search failed: {data.get('error', 'Unknown error')}"}
            else:
                return {"error": f"HTTP {response.status_code}: {response.text}"}
                
        except Exception as e:
            return {"error": f"Search request failed: {str(e)}"}
    
    def _process_search_results(self, data: Dict, search_config: Dict) -> Dict:
        """Process and structure the search results."""
        results = {
            "search_config": search_config,
            "timestamp": datetime.now().isoformat(),
            "web_results": [],
            "news_results": [],
            "images_results": [],
            "total_results": 0,
            "scraped_content": []
        }
        
        # Process web results
        if "web" in data:
            results["web_results"] = data["web"]
            results["total_results"] += len(data["web"])
            
            # Extract scraped content
            for item in data["web"]:
                if "markdown" in item and item["markdown"]:
                    results["scraped_content"].append({
                        "url": item.get("url"),
                        "title": item.get("title"),
                        "content": item["markdown"],
                        "links": item.get("links", [])
                    })
        
        # Process news results
        if "news" in data:
            results["news_results"] = data["news"]
            results["total_results"] += len(data["news"])
        
        # Process image results
        if "images" in data:
            results["images_results"] = data["images"]
            results["total_results"] += len(data["images"])
        
        return results
    
    def save_results(self, results: Dict, output_dir: Path, query_name: str) -> Path:
        """Save search results to file."""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"intelligence_search_{query_name}_{timestamp}.json"
        output_path = output_dir / filename
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        return output_path

def run_segment_searches(segment_config: Dict, output_dir: Path) -> List[Dict]:
    """Run all enhanced searches for a segment."""
    searcher = IntelligenceFirecrawlSearch()
    segment_results = []
    
    segment_name = segment_config.get("name", "Unknown")
    print(f"Running enhanced searches for: {segment_name}")
    
    for i, search_config in enumerate(segment_config.get("enhanced_searches", [])):
        print(f"  Search {i+1}/{len(segment_config['enhanced_searches'])}")
        
        # Run the search
        results = searcher.enhanced_search(search_config, limit=5, scrape_content=True)
        
        if "error" not in results:
            # Save results
            query_name = f"{segment_name.lower().replace(' ', '_')}_search_{i+1}"
            output_path = searcher.save_results(results, output_dir, query_name)
            
            results["output_file"] = str(output_path)
            results["status"] = "success"
            print(f"    ✓ Found {results['total_results']} results, {len(results['scraped_content'])} scraped")
        else:
            results["status"] = "failed"
            print(f"    ✗ Search failed: {results['error']}")
        
        segment_results.append(results)
    
    return segment_results

if __name__ == "__main__":
    # Test with a single search
    test_config = {
        "query": "SMB hiring challenges 2025 recruitment pain points",
        "sources": ["web", "news"],
        "tbs": "qdr:m",
        "categories": ["research"]
    }
    
    searcher = IntelligenceFirecrawlSearch()
    results = searcher.enhanced_search(test_config)
    
    if "error" not in results:
        print(f"Test successful: {results['total_results']} results found")
    else:
        print(f"Test failed: {results['error']}")
