#!/usr/bin/env python3
import argparse, json, os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from firecrawl import Firecrawl

def main():
    ap = argparse.ArgumentParser(description="Extract structured data with Firecrawl")
    ap.add_argument("--urls", nargs="*", required=True, help="URLs to extract from")
    ap.add_argument("--outdir", default="extracted", help="Output directory")
    ap.add_argument("--prompt", 
                    default="Extract key insights about hiring trends, challenges, and strategies for SMBs and global talent acquisition", 
                    help="Extraction prompt")
    args = ap.parse_args()
    
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Firecrawl client
    fc = Firecrawl()
    
    # Schema for structured extraction
    schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "Article title"},
            "summary": {"type": "string", "description": "Executive summary of the content"},
            "key_insights": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of key insights and trends mentioned"
            },
            "challenges_mentioned": {
                "type": "array", 
                "items": {"type": "string"},
                "description": "Hiring challenges or pain points discussed"
            },
            "strategies_solutions": {
                "type": "array",
                "items": {"type": "string"}, 
                "description": "Strategies, solutions, or recommendations provided"
            },
            "statistics": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Important statistics, percentages, or data points"
            },
            "relevance_to_eor": {"type": "string", "description": "How this content relates to EOR/global hiring services"}
        },
        "required": ["title", "summary", "key_insights"]
    }
    
    print(f"Extracting structured data from {len(args.urls)} URLs...")
    
    try:
        res = fc.extract(
            urls=args.urls,
            prompt=args.prompt,
            schema=schema
        )
        
        # Save results
        results_path = outdir / f"{ts}_extraction_results.json"
        results_path.write_text(json.dumps(res.model_dump(), indent=2, ensure_ascii=False))
        print(f"Saved structured extraction: {results_path}")
        
        # Create readable summary
        if hasattr(res, 'data') and res.data:
            readable_content = "# Structured Content Extraction\n\n"
            for i, item in enumerate(res.data, 1):
                if hasattr(item, 'model_dump'):
                    data = item.model_dump()
                else:
                    data = item
                    
                readable_content += f"## Source {i}: {data.get('title', 'Untitled')}\n\n"
                readable_content += f"**Summary:** {data.get('summary', 'No summary')}\n\n"
                
                if data.get('key_insights'):
                    readable_content += "**Key Insights:**\n"
                    for insight in data['key_insights']:
                        readable_content += f"- {insight}\n"
                    readable_content += "\n"
                
                if data.get('strategies_solutions'):
                    readable_content += "**Strategies & Solutions:**\n"
                    for strategy in data['strategies_solutions']:
                        readable_content += f"- {strategy}\n"
                    readable_content += "\n"
                
                readable_content += "---\n\n"
            
            readable_path = outdir / f"{ts}_extraction_readable.md"
            readable_path.write_text(readable_content)
            print(f"Saved readable extraction: {readable_path}")
        
    except Exception as e:
        print(f"Error during extraction: {e}")
        # Save error info
        error_path = outdir / f"{ts}_extraction_error.txt"
        error_path.write_text(f"Extraction failed: {e}")

def sanitize_url_to_filename(url: str) -> str:
    clean = url.replace("https://", "").replace("http://", "")
    clean = clean.replace("/", "_").replace("?", "_").replace("&", "_")
    clean = clean.replace("=", "_").replace("#", "_").replace(":", "_")
    while "__" in clean:
        clean = clean.replace("__", "_")
    return clean.strip("_")[:80]

if __name__ == "__main__":
    main()
