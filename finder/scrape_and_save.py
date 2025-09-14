#!/usr/bin/env python3
import argparse, json, os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from firecrawl import Firecrawl

def main():
    ap = argparse.ArgumentParser(description="Scrape URLs with Firecrawl and save content")
    ap.add_argument("--urls", nargs="*", help="URLs to scrape")
    ap.add_argument("--outdir", default="scraped", help="Output directory")
    ap.add_argument("--formats", nargs="*", default=["markdown", "html"], help="Output formats")
    args = ap.parse_args()

    # Default URLs if none provided
    default_urls = [
        "https://business.linkedin.com/talent-solutions/resources/future-of-recruiting",
        "https://www.remotepass.com/blog/how-smbs-can-compete-for-top-talent-in-a-global-hiring-market-in-2025"
    ]
    
    urls = args.urls if args.urls else default_urls
    
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Firecrawl client
    fc = Firecrawl()
    
    print(f"Scraping {len(urls)} URLs...")
    
    results = []
    for i, url in enumerate(urls, start=1):
        print(f"[{i}/{len(urls)}] Scraping: {url}")
        
        try:
            doc = fc.scrape(url, formats=args.formats)
            
            # Generate filename from URL
            filename = sanitize_url_to_filename(url)
            
            # Save markdown if available
            if hasattr(doc, 'markdown') and doc.markdown:
                md_path = outdir / f"{ts}_{filename}.md"
                md_path.write_text(doc.markdown, encoding='utf-8')
                print(f"  -> Saved markdown: {md_path}")
            
            # Save HTML if available
            if hasattr(doc, 'html') and doc.html:
                html_path = outdir / f"{ts}_{filename}.html"
                html_path.write_text(doc.html, encoding='utf-8')
                print(f"  -> Saved HTML: {html_path}")
            
            # Save metadata
            metadata = {
                "url": url,
                "scraped_at": ts,
                "title": getattr(doc, 'title', None),
                "description": getattr(doc, 'description', None),
                "formats_saved": []
            }
            
            if hasattr(doc, 'markdown') and doc.markdown:
                metadata["formats_saved"].append("markdown")
            if hasattr(doc, 'html') and doc.html:
                metadata["formats_saved"].append("html")
            
            results.append(metadata)
            
        except Exception as e:
            print(f"  ✗ Failed to scrape {url}: {e}")
            results.append({
                "url": url,
                "scraped_at": ts,
                "error": str(e)
            })
    
    # Save summary metadata
    summary_path = outdir / f"{ts}_scrape_summary.json"
    summary_path.write_text(json.dumps({
        "timestamp": ts,
        "total_urls": len(urls),
        "successful": len([r for r in results if "error" not in r]),
        "failed": len([r for r in results if "error" in r]),
        "results": results
    }, indent=2))
    print(f"\nSaved summary: {summary_path}")

def sanitize_url_to_filename(url: str) -> str:
    """Convert URL to safe filename"""
    # Remove protocol
    clean = url.replace("https://", "").replace("http://", "")
    # Replace slashes and other chars
    clean = clean.replace("/", "_").replace("?", "_").replace("&", "_")
    clean = clean.replace("=", "_").replace("#", "_").replace(":", "_")
    # Remove consecutive underscores and trim
    while "__" in clean:
        clean = clean.replace("__", "_")
    clean = clean.strip("_")
    # Limit length
    return clean[:80]

if __name__ == "__main__":
    main()
