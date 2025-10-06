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

    def log(message: str, level: str = "info", **extra_fields: Any) -> None:
        log_method = getattr(logger, level, logger.info)
        payload = {"segment_name": segment_name, "operation": "voc_discovery"}
        payload.update(extra_fields)
        log_method(message, extra=payload)
        logs.append({"timestamp": time.time(), "level": level, "message": message})

    log("Initializing VOC Discovery", level="info")

    logger.debug(
        f"segment_config parameter: {segment_config}",
        extra={"segment_name": segment_name, "operation": "voc_discovery"},
    )
    logger.debug(
        f"Attempting to load config for: {segment_name}",
        extra={"segment_name": segment_name, "operation": "voc_discovery"},
    )
    try:
        if segment_config:
            logger.info(
                "Using provided config overrides: %s",
                list(segment_config.keys()),
                extra={"segment_name": segment_name, "operation": "voc_discovery"},
            )
        else:
            logger.info(
                f"Loading config from file for segment: {segment_name}",
                extra={"segment_name": segment_name, "operation": "voc_discovery"},
            )
        config = segment_config or load_segment_config(segment_name)
    except FileNotFoundError as exc:
        raise VOCDiscoveryError(str(exc)) from exc

    logger.debug(
        f"Final config subreddits: {config.get('subreddits', [])}",
        extra={"segment_name": segment_name, "operation": "voc_discovery"},
    )

    reddit_api_key = os.environ.get("SCRAPECREATORS_API_KEY")
    if not reddit_api_key:
        logger.error(
            "SCRAPECREATORS_API_KEY missing",
            extra={"segment_name": segment_name, "operation": "voc_discovery"},
        )
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

    fetch_start = time.perf_counter()
    reddit_posts, raw_unfiltered_posts, reddit_warnings = collector.fetch_posts(
        segment_name=segment_name,
        segment_config=config,
        log_callback=log,
    )
    fetch_duration = round((time.perf_counter() - fetch_start) * 1000, 2)
    logger.info(
        "Reddit fetch completed",
        extra={
            "segment_name": segment_name,
            "operation": "reddit_fetch",
            "count": len(reddit_posts),
            "duration_ms": fetch_duration,
        },
    )
    warnings.extend(reddit_warnings)
    log(f"Collected {len(reddit_posts)} candidate Reddit posts")

    enriched_posts: List[Dict[str, Any]] = []
    enrich_start = time.perf_counter()
    for post in reddit_posts:
        enriched, post_warnings = collector.enrich_post(
            post,
            segment_name=segment_name,
            segment_config=config,
        )
        warnings.extend(post_warnings)
        enriched_posts.append(enriched)
    logger.info(
        "Reddit enrichment completed",
        extra={
            "segment_name": segment_name,
            "operation": "reddit_enrich",
            "count": len(enriched_posts),
            "duration_ms": round((time.perf_counter() - enrich_start) * 1000, 2),
        },
    )

    processed_ids = [post.get("id") for post in enriched_posts]
    history_store.mark(segment_name, [pid for pid in processed_ids if pid])

    min_score = float(config.get("ai_min_score", 6.0))
    logger.debug(
        "Applying AI relevance filter",
        extra={
            "segment_name": segment_name,
            "operation": "reddit_filter",
            "min_score": min_score,
        },
    )
    high_value_posts, rejected_posts = filter_high_value_posts(enriched_posts, min_score=min_score)
    log(f"{len(high_value_posts)} posts passed AI relevance threshold ({min_score})")

    trends_start = time.perf_counter()
    trends_data, trends_warnings = fetch_google_trends(config)
    logger.info(
        "Google Trends fetch completed",
        extra={
            "segment_name": segment_name,
            "operation": "trends_fetch",
            "count": len(trends_data),
            "duration_ms": round((time.perf_counter() - trends_start) * 1000, 2),
        },
    )
    warnings.extend(trends_warnings)
    log(f"Collected Google Trends data for {len(trends_data)} keywords")

    queries_start = time.perf_counter()
    curated_queries, query_warnings = generate_curated_queries(
        high_value_posts,
        trends_data,
        config,
        segment_name=segment_name,
        gemini_client=gemini_client,
    )
    logger.info(
        "Curated query generation completed",
        extra={
            "segment_name": segment_name,
            "operation": "query_generation",
            "count": len(curated_queries),
            "duration_ms": round((time.perf_counter() - queries_start) * 1000, 2),
        },
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

