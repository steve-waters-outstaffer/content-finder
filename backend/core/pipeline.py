"""Main content pipeline orchestrator"""
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
import json

from .firecrawl_client import FirecrawlClient
from .gemini_client import GeminiClient


class ContentPipeline:
    """Orchestrates the full content discovery and analysis pipeline"""
    
    def __init__(self, firecrawl_api_key: Optional[str] = None, gemini_api_key: Optional[str] = None):
        """Initialize pipeline with API clients"""
        # Use provided keys or fallback to environment variables
        firecrawl_key = firecrawl_api_key or os.environ.get('FIRECRAWL_API_KEY')
        gemini_key = gemini_api_key or os.environ.get('GEMINI_API_KEY')
        
        self.firecrawl = FirecrawlClient(api_key=firecrawl_key)
        self.gemini = GeminiClient(api_key=gemini_key)
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def run_full_pipeline(self, query: str, max_urls: int = 3, output_dir: Optional[Path] = None) -> Dict[str, Any]:
        """Run complete pipeline: search -> scrape -> extract -> analyze"""
        
        if output_dir is None:
            output_dir = Path("pipeline_output")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        pipeline_result = {
            'query': query,
            'timestamp': self.timestamp,
            'max_urls': max_urls,
            'steps': {}
        }
        
        # Step 1: Search
        print(f"1️⃣ SEARCHING: '{query}'")
        search_result = self.firecrawl.search(query, limit=max_urls * 2)  # Get extra results to filter
        pipeline_result['steps']['search'] = search_result
        
        if not search_result.get('results'):
            pipeline_result['error'] = 'No search results found'
            return pipeline_result
        
        # Extract URLs from search results
        urls = []
        for item in search_result['results'][:max_urls]:
            url = getattr(item, 'url', None) if hasattr(item, 'url') else item.get('url')
            if url:
                urls.append(url)
        
        print(f"📝 Found {len(urls)} URLs to process")
        pipeline_result['urls'] = urls
        
        # Step 2: Scrape
        print(f"2️⃣ SCRAPING: {len(urls)} URLs")
        scrape_results = self.firecrawl.scrape_urls(urls)
        pipeline_result['steps']['scrape'] = scrape_results
        
        successful_scrapes = [r for r in scrape_results if r.get('success', False)]
        print(f"✓ Successfully scraped {len(successful_scrapes)}/{len(urls)} URLs")
        
        # Step 3: Extract structured data
        print(f"3️⃣ EXTRACTING: Structured data from {len(urls)} URLs")
        extraction_result = self.firecrawl.extract_structured(urls)
        pipeline_result['steps']['extract'] = extraction_result
        
        if extraction_result.get('success'):
            print("✓ Structured extraction completed")
        else:
            print(f"⚠️ Extraction failed: {extraction_result.get('error', 'Unknown error')}")
        
        # Step 4: Analyze with AI
        print(f"4️⃣ ANALYZING: Content with Gemini")
        analyses = []
        for scrape_result in successful_scrapes:
            if scrape_result.get('markdown'):
                print(f"🤖 Analyzing: {scrape_result['url']}")
                analysis = self.gemini.analyze_article_structured(scrape_result['markdown'])
                analyses.append(
                    {
                        "source_url": scrape_result['url'],
                        "analysis": analysis.model_dump(),
                    }
                )

        pipeline_result['steps']['analyze'] = analyses
        print(f"✓ Analyzed {len(analyses)}/{len(successful_scrapes)} scraped documents")
        
        # Save results
        self._save_pipeline_results(pipeline_result, output_dir)
        
        return pipeline_result
    
    def search_only(self, query: str, limit: int = 15) -> Dict[str, Any]:
        """Run search-only operation"""
        return self.firecrawl.search(query, limit)
    
    def scrape_urls(self, urls: List[str]) -> List[Dict[str, Any]]:
        """Run scraping-only operation"""
        return self.firecrawl.scrape_urls(urls)
    
    def analyze_content(self, content: str, custom_prompt: str = None) -> Dict[str, Any]:
        """Run analysis-only operation"""

        analysis = self.gemini.analyze_article_structured(
            content,
            additional_instructions=custom_prompt,
        )

        return analysis.model_dump()

    def synthesize_article(self, query: str, contents: List[Dict[str, str]]) -> Dict[str, Any]:
        """Passes multiple documents to Gemini for synthesis."""
        synthesis = self.gemini.synthesize_multi_article_analysis(query, contents)
        return synthesis.model_dump()

    def _save_pipeline_results(self, results: Dict[str, Any], output_dir: Path):
        """Save pipeline results to files"""
        # Save complete pipeline results
        pipeline_file = output_dir / f"pipeline_results_{self.timestamp}.json"
        with open(pipeline_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False, default=str)
        print(f"📊 Pipeline results saved: {pipeline_file}")
        
        # Save scraped content as individual markdown files
        scraped_dir = output_dir / "scraped"
        scraped_dir.mkdir(exist_ok=True)
        
        scrape_results = results.get('steps', {}).get('scrape', [])
        for i, result in enumerate(scrape_results):
            if result.get('success') and result.get('markdown'):
                filename = self._sanitize_filename(result['url'])
                md_file = scraped_dir / f"{self.timestamp}_{filename}.md"
                with open(md_file, 'w', encoding='utf-8') as f:
                    f.write(result['markdown'])
        
        # Save analyses as readable markdown
        if results.get('steps', {}).get('analyze'):
            analysis_dir = output_dir / "analysis"
            analysis_dir.mkdir(exist_ok=True)
            
            for i, analysis in enumerate(results['steps']['analyze']):
                if analysis.get('success'):
                    source_filename = self._sanitize_filename(analysis.get('source_url', f'analysis_{i}'))
                    analysis_file = analysis_dir / f"{self.timestamp}_{source_filename}_analysis.md"
                    
                    content = f"# Content Analysis\n\n"
                    content += f"**Source:** {analysis.get('source_url', 'Unknown')}\n"
                    content += f"**Analyzed:** {analysis.get('analyzed_at', 'Unknown')}\n\n"
                    content += "---\n\n"
                    content += analysis.get('analysis', 'No analysis available')
                    
                    with open(analysis_file, 'w', encoding='utf-8') as f:
                        f.write(content)
    
    def _sanitize_filename(self, url: str) -> str:
        """Convert URL to safe filename"""
        clean = url.replace("https://", "").replace("http://", "")
        clean = clean.replace("/", "_").replace("?", "_").replace("&", "_")
        clean = clean.replace("=", "_").replace("#", "_").replace(":", "_")
        while "__" in clean:
            clean = clean.replace("__", "_")
        return clean.strip("_")[:80]
