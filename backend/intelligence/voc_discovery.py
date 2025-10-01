"""Lean orchestrator for the Voice of Customer discovery workflow."""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.gemini_client import GeminiClient, GeminiClientError
from intelligence.voc_reddit import (
    RedditDataCollector,
    RedditHistoryStore,
    load_segment_config,
)
from intelligence.voc_synthesis import filter_high_value_posts, generate_curated_queries
from intelligence.voc_trends import fetch_google_trends

logger = logging.getLogger(__name__)


class VOCDiscoveryError(RuntimeError):
    """Raised when the discovery workflow encounters a fatal error."""


def _load_intelligence_config() -> Dict[str, Any]:
    config_path = Path(__file__).resolve().parent / "config" / "intelligence_config.json"
    if not config_path.exists():
        return {}
    try:
        return json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def run_voc_discovery(
    segment_name: str,
    segment_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    warnings: List[str] = []
    logs: List[Dict[str, Any]] = []

    def log(message: str, level: str = "info") -> None:
        log_method = getattr(logger, level, logger.info)
        log_method(message)
        logs.append({"timestamp": time.time(), "level": level, "message": message})

    log(f"Initializing VOC Discovery for segment: {segment_name}")

    try:
        config = segment_config or load_segment_config(segment_name)
    except FileNotFoundError as exc:
        raise VOCDiscoveryError(str(exc)) from exc

    reddit_api_key = os.environ.get("SCRAPECREATORS_API_KEY")
    if not reddit_api_key:
        raise VOCDiscoveryError("SCRAPECREATORS_API_KEY environment variable is required.")

    try:
        gemini_client = GeminiClient()
    except GeminiClientError as exc:
        raise VOCDiscoveryError(str(exc)) from exc

    history_store = RedditHistoryStore.create()
    collector = RedditDataCollector(
        api_key=reddit_api_key,
        gemini_client=gemini_client,
        history_store=history_store,
    )

    reddit_posts, reddit_warnings = collector.fetch_posts(
        segment_name=segment_name,
        segment_config=config,
        log_callback=log,
    )
    warnings.extend(reddit_warnings)
    log(f"Collected {len(reddit_posts)} candidate Reddit posts")

    enriched_posts: List[Dict[str, Any]] = []
    for post in reddit_posts:
        enriched, post_warnings = collector.enrich_post(
            post,
            segment_name=segment_name,
            segment_config=config,
        )
        warnings.extend(post_warnings)
        enriched_posts.append(enriched)

    processed_ids = [post.get("id") for post in enriched_posts]
    history_store.mark(segment_name, [pid for pid in processed_ids if pid])

    min_score = float(config.get("ai_min_score", 6.0))
    high_value_posts, rejected_posts = filter_high_value_posts(enriched_posts, min_score=min_score)
    log(f"{len(high_value_posts)} posts passed AI relevance threshold ({min_score})")

    trends_data, trends_warnings = fetch_google_trends(config)
    warnings.extend(trends_warnings)
    log(f"Collected Google Trends data for {len(trends_data)} keywords")

    curated_queries, query_warnings = generate_curated_queries(
        high_value_posts,
        trends_data,
        config,
        segment_name=segment_name,
        gemini_client=gemini_client,
    )
    warnings.extend(query_warnings)

    results: Dict[str, Any] = {
        "segment": segment_name,
        "reddit_posts": high_value_posts,
        "reddit_posts_low_score": rejected_posts,
        "google_trends": trends_data,
        "curated_queries": curated_queries,
        "warnings": warnings,
        "logs": logs,
    }

    intelligence_config = _load_intelligence_config()
    monthly_segments = intelligence_config.get("monthly_run", {}).get("segments", [])
    segment_meta = next((s for s in monthly_segments if s.get("name") == segment_name), {})
    if segment_meta:
        results["segment_metadata"] = segment_meta

    return results


__all__ = ["run_voc_discovery", "VOCDiscoveryError"]

