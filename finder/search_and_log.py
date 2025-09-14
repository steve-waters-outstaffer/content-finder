#!/usr/bin/env python3
import argparse, csv, json, os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from firecrawl import Firecrawl

def main():
    ap = argparse.ArgumentParser(description="Firecrawl search → log results")
    ap.add_argument("query", help="Search query")
    ap.add_argument("--limit", type=int, default=15, help="Max web results")
    ap.add_argument("--outdir", default="out", help="Output directory")
    ap.add_argument("--scrape-top", type=int, default=0, help="Also scrape top N URLs to markdown")
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = f"search_{ts}"

    # Firecrawl client (reads FIRECRAWL_API_KEY env or pass api_key=...)
    fc = Firecrawl()

    # ---- Search ----
    res = fc.search(query=args.query, limit=args.limit)
    web: List[Dict[str, Any]] = res.web or []

    if not web:
        print("No web results.")
        return

    # Write raw payload
    raw_path = outdir / f"{stem}_raw.json"
    # Convert Pydantic model to dict for JSON serialization
    raw_path.write_text(json.dumps(res.model_dump(), ensure_ascii=False, indent=2))
    print(f"Saved raw JSON -> {raw_path}")

    # Write flat JSONL
    jsonl_path = outdir / f"{stem}.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as f:
        for item in web:
            f.write(json.dumps({
                "query": args.query,
                "position": getattr(item, "position", None),
                "title": getattr(item, "title", None),
                "url": getattr(item, "url", None),
                "description": getattr(item, "description", None),
                "fetched_at": ts
            }, ensure_ascii=False) + "\n")
    print(f"Saved JSONL -> {jsonl_path}")

    # Write CSV
    csv_path = outdir / f"{stem}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["query","position","title","url","description","fetched_at"])
        w.writeheader()
        for item in web:
            w.writerow({
                "query": args.query,
                "position": getattr(item, "position", None),
                "title": (getattr(item, "title", "") or "").strip(),
                "url": getattr(item, "url", None),
                "description": (getattr(item, "description", "") or "").strip(),
                "fetched_at": ts
            })
    print(f"Saved CSV -> {csv_path}")

    # ---- Optional: scrape top N to markdown ----
    n = max(0, min(args.scrape_top, len(web)))
    if n:
        md_dir = outdir / f"{stem}_markdown"
        md_dir.mkdir(parents=True, exist_ok=True)
        for i, item in enumerate(web[:n], start=1):
            url = getattr(item, "url", None)
            try:
                doc = fc.scrape(url, formats=["markdown"])
                md = (doc.get("markdown") or "") if isinstance(doc, dict) else ""
                (md_dir / f"{i:02d}_{sanitize(getattr(item, 'title', '') or 'untitled')}.md").write_text(md)
                print(f"[{i}/{n}] scraped -> {url}")
            except Exception as e:
                print(f"[{i}/{n}] scrape failed for {url}: {e}")

def sanitize(s: str) -> str:
    return "".join(ch for ch in s if ch.isalnum() or ch in ("-", "_", " ")).strip().replace(" ", "_")[:80]

if __name__ == "__main__":
    main()
