"""AI synthesis helpers for VOC discovery."""

from __future__ import annotations

import html
import json
import logging
import time
from typing import Any, Dict, List, Sequence, Tuple

import instructor
import asyncio
from pydantic import BaseModel, Field
from typing import Optional

from core.gemini_client import GeminiClient, GeminiClientError

logger = logging.getLogger(__name__)


class PostScore(BaseModel):
    post_index: int = Field(description="Index of the post in the batch")
    relevance_score: float = Field(ge=0.0, le=10.0, description="Score from 0-10")
    quick_reason: str = Field(max_length=200, description="Brief reason for score")


def clean_text_for_json(text: str, max_length: int = 1500) -> str:
    """
    Clean text to prevent JSON issues while preserving readability.
    Handles quotes, newlines, special characters, and HTML entities.
    
    Args:
        text: Raw text to clean
        max_length: Maximum character length (default 1500)
    
    Returns:
        Cleaned text safe for JSON encoding
    """
    if not text:
        return ""
    
    # HTML decode first (handles &amp;, &quot;, etc.)
    text = html.unescape(text)
    
    # Replace problematic characters
    text = text.replace('\r\n', ' ')  # Windows newlines
    text = text.replace('\n', ' ')     # Unix newlines
    text = text.replace('\t', ' ')     # Tabs
    text = text.replace('"', "'")      # Double quotes → single (safer in JSON strings)
    text = text.replace('\\', '')      # Remove backslashes
    
    # Collapse multiple spaces
    text = ' '.join(text.split())
    
    # Truncate to max length
    return text[:max_length].strip()


def _strip_post_for_prescore(post: Dict[str, Any]) -> Dict[str, Any]:
    """
    Strip Reddit post to minimal fields needed for pre-scoring.
    Reduces token usage while preserving essential context.
    Cleans content to prevent JSON parsing errors.
    """
    selftext = post.get("content_snippet", "") or post.get("selftext", "")
    
    return {
        "id": post.get("id", ""),
        "title": clean_text_for_json(post.get("title", ""), max_length=200),
        "subreddit": post.get("subreddit", ""),
        "score": post.get("score", 0),
        "num_comments": post.get("num_comments", 0),
        "content": clean_text_for_json(selftext, max_length=1000),
    }


async def score_single_post_async(
    instructor_client,
    post: Dict[str, Any],
    post_index: int,
    segment_config: Dict[str, Any],
    segment_name: str,
) -> Tuple[Optional[PostScore], Optional[str]]:
    """Score a single post using Instructor with retries."""

    stripped = _strip_post_for_prescore(post)

    prompt = f"""You are analyzing Reddit posts for relevance to: {segment_name}

Target Audience: {segment_config.get('audience', '')}

Key Priorities:
{chr(10).join([f"• {p}" for p in segment_config.get('priorities', [])])}

POST TO SCORE:
Title: {stripped.get('title', '[N/A]')}
Content: {stripped.get('content', '')}

Score from 0-10:
- 8-10: Highly relevant
- 5-7: Moderately relevant
- 0-4: Low relevance

Return: post_index={post_index}, relevance_score (0-10), quick_reason (1-2 sentences)"""

    await asyncio.sleep(0.1)  # Rate limit protection

    try:
        result = await instructor_client.messages.create(
            model="gemini-2.0-flash-exp",
            response_model=PostScore,
            messages=[{"role": "user", "content": prompt}],
            max_retries=3,
            max_tokens=500,
        )
        return result, None
    except Exception as exc:
        error_msg = f"Post {post_index} failed: {str(exc)[:100]}"
        logger.warning(error_msg, extra={"post_index": post_index, "segment_name": segment_name})
        return None, error_msg


async def batch_prescore_posts(
    posts: Sequence[Dict[str, Any]],
    segment_config: Dict[str, Any],
    segment_name: str,
    gemini_client: GeminiClient,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Pre-score posts using parallel async calls with Instructor."""
    
    warnings: List[str] = []
    if not posts:
        return [], warnings
    
    # Patch Gemini client with Instructor
    raw_client = gemini_client._get_client()
    instructor_client = instructor.from_gemini(raw_client, mode=instructor.Mode.GEMINI_JSON)
    
    # Maintain a concrete sequence of the original posts so we can map results
    # directly back by index, preserving duplicates and handling missing IDs.
    original_posts: List[Dict[str, Any]] = list(posts)
    
    logger.info(f"Starting parallel pre-scoring for {len(posts)} posts", extra={"segment_name": segment_name})

    # Create parallel tasks
    tasks = [
        score_single_post_async(instructor_client, post, idx, segment_config, segment_name)
        for idx, post in enumerate(posts)
    ]

    # Execute concurrently
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results
    all_scored_posts = []
    for idx, result in enumerate(results):
        if isinstance(result, Exception):
            warnings.append(f"Unexpected error for post {idx}: {result}")
            continue

        score_obj, error = result
        if error:
            warnings.append(error)
            continue

        # Determine which original post to enrich. Prefer the explicit index
        # returned by the model but fall back to the current loop index. This
        # approach keeps alignment with the original sequence even when IDs are
        # missing or duplicated.
        target_index = idx
        if score_obj and score_obj.post_index is not None:
            target_index = score_obj.post_index

        if target_index < 0 or target_index >= len(original_posts):
            warnings.append(
                f"Post index {target_index} out of range for post {idx}; falling back to loop index"
            )
            target_index = idx

        if target_index >= len(original_posts):
            warnings.append(f"Loop index {idx} out of range; skipping enrichment")
            continue

        original_post = original_posts[target_index]

        # Enrich original post
        enriched = original_post.copy()
        enriched["prescore"] = {
            "relevance_score": score_obj.relevance_score,
            "quick_reason": score_obj.quick_reason,
        }
        all_scored_posts.append(enriched)
    
    success_rate = len(all_scored_posts) / len(posts) if posts else 0
    logger.info(
        f"Pre-scoring complete: {len(all_scored_posts)}/{len(posts)} ({success_rate:.1%})",
        extra={"segment_name": segment_name, "success_rate": success_rate}
    )
    
    return all_scored_posts, warnings


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


__all__ = ["batch_prescore_posts", "filter_high_value_posts", "generate_curated_queries"]
