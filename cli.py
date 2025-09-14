#!/usr/bin/env python3
"""CLI interface for the content finder pipeline using the new backend structure"""
import argparse
import sys
from pathlib import Path

# Add backend to Python path
backend_path = Path(__file__).parent / "backend"
sys.path.insert(0, str(backend_path))

from core.pipeline import ContentPipeline


def main():
    parser = argparse.ArgumentParser(description="Content Finder CLI")
    parser.add_argument("command", choices=["search", "scrape", "analyze", "pipeline"], 
                       help="Command to run")
    parser.add_argument("--query", help="Search query")
    parser.add_argument("--urls", nargs="*", help="URLs to process")
    parser.add_argument("--content", help="Content to analyze")
    parser.add_argument("--limit", type=int, default=15, help="Search result limit")
    parser.add_argument("--max-urls", type=int, default=3, help="Max URLs to process in pipeline")
    parser.add_argument("--output-dir", help="Output directory")
    
    args = parser.parse_args()
    
    # Initialize pipeline
    pipeline = ContentPipeline()
    
    if args.command == "search":
        if not args.query:
            print("Error: --query required for search command")
            return 1
            
        print(f"Searching for: {args.query}")
        result = pipeline.search_only(args.query, args.limit)
        print(f"Found {len(result.get('results', []))} results")
        
    elif args.command == "scrape":
        if not args.urls:
            print("Error: --urls required for scrape command")
            return 1
            
        print(f"Scraping {len(args.urls)} URLs...")
        results = pipeline.scrape_urls(args.urls)
        successful = len([r for r in results if r.get('success')])
        print(f"Successfully scraped {successful}/{len(results)} URLs")
        
    elif args.command == "analyze":
        if not args.content:
            print("Error: --content required for analyze command")
            return 1
            
        print("Analyzing content with Gemini...")
        result = pipeline.analyze_content(args.content)
        if result.get('success'):
            print("Analysis completed successfully")
        else:
            print(f"Analysis failed: {result.get('error')}")
            
    elif args.command == "pipeline":
        if not args.query:
            print("Error: --query required for pipeline command")
            return 1
            
        print(f"Running full pipeline for: {args.query}")
        output_dir = Path(args.output_dir) if args.output_dir else None
        result = pipeline.run_full_pipeline(args.query, args.max_urls, output_dir)
        
        if result.get('error'):
            print(f"Pipeline failed: {result['error']}")
            return 1
        else:
            print("Pipeline completed successfully!")
            print(f"Processed {len(result.get('urls', []))} URLs")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
