"""AI synthesis helpers for VOC discovery."""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Sequence, Tuple

from core.gemini_client import GeminiClient, GeminiClientError

logger = logging.getLogger(__name__)


def filter_high_value_posts(posts: Sequence[Dict[str, Any]], min_score: float = 6.0) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    accepted: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []

    logger.debug(
        "Filtering high value posts",
        extra={
            "operation": "reddit_filter",
            "count": len(posts),
            "min_score": min_score,
        },
    )
    for post in posts:
        analysis = post.get("ai_analysis") or {}
        score = analysis.get("relevance_score")
        if isinstance(score, (int, float)) and score >= min_score:
            accepted.append(post)
        else:
            rejected.append(post)
        logger.debug(
            "Post %s evaluated",
            extra={
                "operation": "reddit_filter",
                "post_id": post.get("id"),
                "score": score,
                "min_score": min_score,
                "accepted": post in accepted,
            },
        )
    logger.info(
        "High value post filtering complete",
        extra={
            "operation": "reddit_filter",
            "count": len(accepted),
            "rejected_count": len(rejected),
        },
    )
    return accepted, rejected


def generate_curated_queries(
    analyzed_posts: Sequence[Dict[str, Any]],
    trends_data: Sequence[Dict[str, Any]],
    segment_config: Dict[str, Any],
    *,
    segment_name: str,
    gemini_client: GeminiClient,
) -> Tuple[List[str], List[str]]:
    pain_point_lines: List[str] = []
    for post in analyzed_posts:
        ai_analysis = post.get("ai_analysis") or {}
        if not isinstance(ai_analysis, dict):
            continue
        pain_point = ai_analysis.get("identified_pain_point") or "(pain point unavailable)"
        relevance = ai_analysis.get("relevance_score")
        title = post.get("title", "")
        subreddit = post.get("subreddit", "")
        if relevance is not None:
            pain_point_lines.append(
                f"- {pain_point} (relevance {relevance}) — r/{subreddit} | {title}"
            )
        else:
            pain_point_lines.append(f"- {pain_point} — r/{subreddit} | {title}")

    trends_lines: List[str] = []
    for trend in trends_data:
        query = trend.get("query")
        if not query:
            continue
        related = trend.get("related_queries", {})
        rising = related.get("rising") if isinstance(related, dict) else []
        rising_terms = ", ".join(
            str(item.get("query"))
            for item in rising[:3]
            if isinstance(item, dict) and item.get("query")
        )
        if rising_terms:
            trends_lines.append(f"- {query}: rising searches include {rising_terms}")
        else:
            trends_lines.append(f"- {query}: steady interest over time")

    if not pain_point_lines and not trends_lines:
        logger.info("Skipping curated query generation - no meaningful data available")
        return [], []

    pain_points = "\n".join(pain_point_lines) if pain_point_lines else "- No AI-analyzed Reddit posts were available."
    trends_summary = "\n".join(trends_lines) if trends_lines else "- Google Trends data unavailable."

    prompt_context = {
        "segment_name": segment_name,
        "audience": segment_config.get("audience", ""),
        "pain_points": pain_points,
        "trends_summary": trends_summary,
    }

    try:
        start_time = time.perf_counter()
        response = gemini_client.generate_json_response(
            "voc_curated_queries_prompt.txt",
            prompt_context,
            temperature=0.3,
            max_output_tokens=1024,
        )
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    except (GeminiClientError, FileNotFoundError) as exc:
        warning = f"Gemini curated query generation failed: {exc}"
        logger.warning(
            warning,
            extra={
                "operation": "query_generation",
                "segment_name": segment_name,
            },
        )
        return [], [warning]

    data = response.data
    if isinstance(data, list):
        cleaned = [str(item).strip() for item in data if str(item).strip()]
        logger.info(
            "Curated queries generated",
            extra={
                "operation": "query_generation",
                "segment_name": segment_name,
                "count": len(cleaned),
                "duration_ms": duration_ms,
            },
        )
        return cleaned, []
    if isinstance(data, dict) and isinstance(data.get("queries"), list):
        cleaned = [str(item).strip() for item in data["queries"] if str(item).strip()]
        logger.info(
            "Curated queries generated",
            extra={
                "operation": "query_generation",
                "segment_name": segment_name,
                "count": len(cleaned),
                "duration_ms": duration_ms,
            },
        )
        return cleaned, []

    warning = "Gemini returned unexpected structure for curated queries generation."
    logger.warning(
        warning,
        extra={
            "operation": "query_generation",
            "segment_name": segment_name,
        },
    )
    return [], [warning]


__all__ = ["filter_high_value_posts", "generate_curated_queries"]

