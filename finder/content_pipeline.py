#!/usr/bin/env python3
import argparse, json, os, subprocess, sys
from datetime import datetime
from pathlib import Path

def main():
    ap = argparse.ArgumentParser(description="Full content pipeline: search → scrape → extract → analyze")
    ap.add_argument("query", help="Search query")
    ap.add_argument("--limit", type=int, default=10, help="Max search results")
    ap.add_argument("--scrape-top", type=int, default=3, help="Scrape top N URLs")
    ap.add_argument("--outdir", default="pipeline_output", help="Output directory")
    ap.add_argument("--skip-search", action="store_true", help="Skip search, use provided URLs")
    ap.add_argument("--urls", nargs="*", help="URLs to process (if skipping search)")
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    print("🔍 CONTENT PIPELINE STARTING")
    print("="*50)
    
    # Step 1: Search (unless skipped)
    if args.skip_search and args.urls:
        urls_to_scrape = args.urls[:args.scrape_top]
        print(f"⏩ Skipping search, using provided URLs: {len(urls_to_scrape)} URLs")
    else:
        print(f"1️⃣  SEARCHING: '{args.query}' (limit: {args.limit})")
        search_cmd = [
            sys.executable, "search_and_log.py", 
            args.query,
            "--limit", str(args.limit),
            "--outdir", str(outdir / "search")
        ]
        
        try:
            result = subprocess.run(search_cmd, capture_output=True, text=True, check=True)
            print("✓ Search completed")
            
            # Find the latest search results
            search_files = list((outdir / "search").glob("search_*_raw.json"))
            if not search_files:
                print("❌ No search results found")
                return
            
            latest_search = max(search_files, key=lambda x: x.stat().st_mtime)
            search_data = json.loads(latest_search.read_text())
            
            # Extract URLs from search results
            web_results = search_data.get('web', [])
            urls_to_scrape = []
            for item in web_results[:args.scrape_top]:
                url = getattr(item, 'url', None) if hasattr(item, 'url') else item.get('url')
                if url:
                    urls_to_scrape.append(url)
            
            print(f"📝 Found {len(urls_to_scrape)} URLs to scrape from search results")
            
        except subprocess.CalledProcessError as e:
            print(f"❌ Search failed: {e}")
            print("STDOUT:", e.stdout)
            print("STDERR:", e.stderr)
            return
    
    if not urls_to_scrape:
        print("❌ No URLs to scrape")
        return
    
    # Step 2: Scrape
    print(f"\n2️⃣  SCRAPING: {len(urls_to_scrape)} URLs")
    scrape_cmd = [
        sys.executable, "scrape_and_save.py",
        "--urls"] + urls_to_scrape + [
        "--outdir", str(outdir / "scraped")
    ]
    
    try:
        result = subprocess.run(scrape_cmd, capture_output=True, text=True, check=True)
        print("✓ Scraping completed")
        
        # Find scraped markdown files
        scraped_files = list((outdir / "scraped").glob("*.md"))
        if not scraped_files:
            print("❌ No scraped content found")
            return
            
        print(f"📄 Scraped {len(scraped_files)} markdown files")
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Scraping failed: {e}")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        return
    
    # Step 3: Extract structured data using Firecrawl
    print(f"\n3️⃣  EXTRACTING: Structured data from scraped content")
    
    # Use Firecrawl extract on the original URLs
    extract_cmd = [
        sys.executable, "extract_structured.py",
        "--urls"] + urls_to_scrape + [
        "--outdir", str(outdir / "extracted")
    ]
    
    try:
        result = subprocess.run(extract_cmd, capture_output=True, text=True, check=True)
        print("✓ Extraction completed")
        
    except subprocess.CalledProcessError as e:
        print(f"⚠️  Extraction failed, continuing with scraped content: {e}")
    
    # Step 4: Analyze with Gemini
    print(f"\n4️⃣  ANALYZING: Content with Gemini")
    
    # Analyze each scraped file
    analyzed_count = 0
    for md_file in scraped_files:
        if md_file.name.endswith('_summary.json'):
            continue  # Skip summary files
            
        print(f"🤖 Analyzing: {md_file.name}")
        
        analyze_cmd = [
            sys.executable, "analyze_with_gemini.py",
            "--content-file", str(md_file),
            "--outdir", str(outdir / "analysis")
        ]
        
        try:
            result = subprocess.run(analyze_cmd, capture_output=True, text=True, check=True)
            analyzed_count += 1
            print(f"✓ Analysis {analyzed_count} completed")
            
        except subprocess.CalledProcessError as e:
            print(f"⚠️  Analysis failed for {md_file.name}: {e}")
            continue
    
    # Step 5: Create consolidated summary
    print(f"\n5️⃣  CONSOLIDATING: Final summary")
    
    summary_data = {
        "pipeline_run": ts,
        "query": args.query,
        "urls_processed": urls_to_scrape,
        "files_scraped": len(scraped_files),
        "files_analyzed": analyzed_count,
        "output_directory": str(outdir)
    }
    
    # Save pipeline summary
    summary_path = outdir / f"pipeline_summary_{ts}.json"
    summary_path.write_text(json.dumps(summary_data, indent=2))
    
    # Create a quick markdown index
    index_content = f"""# Content Pipeline Results

**Run Date:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Query:** {args.query}
**URLs Processed:** {len(urls_to_scrape)}

## Output Structure
- `search/` - Search results and raw data
- `scraped/` - Full scraped content in markdown
- `extracted/` - Structured data extraction (if successful)
- `analysis/` - Gemini AI analysis of content

## Quick Links
"""
    
    # Add links to analysis files
    analysis_files = list((outdir / "analysis").glob("*_clean.md"))
    for i, analysis_file in enumerate(analysis_files, 1):
        index_content += f"- [Analysis {i}]({analysis_file.relative_to(outdir)})\n"
    
    index_path = outdir / "README.md"
    index_path.write_text(index_content)
    
    print("="*50)
    print("🎉 PIPELINE COMPLETED!")
    print(f"📁 Results saved to: {outdir}")
    print(f"📊 Processed {len(urls_to_scrape)} URLs")
    print(f"📄 Scraped {len(scraped_files)} files")  
    print(f"🤖 Analyzed {analyzed_count} files")
    print(f"📋 Summary: {index_path}")

if __name__ == "__main__":
    main()
