"""AI synthesis helpers for VOC discovery."""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Sequence, Tuple

from core.gemini_client import GeminiClient, GeminiClientError

logger = logging.getLogger(__name__)


def _escape_for_json(text: str) -> str:
    """
    Escape text to prevent JSON parsing issues.
    Handles quotes, newlines, and other special characters.
    """
    if not text:
        return ""
    # Replace problematic characters that break JSON strings
    # Order matters: backslashes first, then other escapes
    return (
        text.replace("\\", "\\\\")  # Backslashes first
        .replace('"', '\\"')        # Double quotes
        .replace("'", "\\'")        # Single quotes (can break in some contexts)
        .replace("\n", " ")         # Newlines to spaces
        .replace("\r", " ")         # Carriage returns
        .replace("\t", " ")         # Tabs
        .replace("\b", " ")         # Backspace
        .replace("\f", " ")         # Form feed
    )


def _strip_post_for_prescore(post: Dict[str, Any]) -> Dict[str, Any]:
    """
    Strip Reddit post to minimal fields needed for pre-scoring.
    Reduces token usage by ~95% while preserving essential context.
    Escapes content to prevent JSON parsing errors.
    """
    selftext = post.get("content_snippet", "") or post.get("selftext", "")
    
    return {
        "id": post.get("id", ""),
        "title": _escape_for_json(post.get("title", "")),
        "subreddit": post.get("subreddit", ""),
        "score": post.get("score", 0),
        "num_comments": post.get("num_comments", 0),
        "selftext": _escape_for_json(selftext[:750]) if selftext else "",  # Truncate then escape
    }


def batch_prescore_posts(
    posts: Sequence[Dict[str, Any]],
    segment_config: Dict[str, Any],
    segment_name: str,
    gemini_client: GeminiClient,
    batch_size: int = 25,  # Reduced from 50 to avoid token limits with stripped data
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Stage 1: Batch pre-score posts using only title + snippet (no comments).
    Fast, lightweight analysis to filter down to promising posts.
    
    Posts are stripped to minimal fields (id, title, subreddit, score, num_comments, 
    selftext[:750]) before sending to Gemini to reduce token usage by ~95%.
    """
    warnings: List[str] = []
    
    if not posts:
        return [], warnings
    
    all_scored_posts = []
    
    # Keep full posts in memory for matching back after scoring
    posts_by_id = {post.get("id"): post for post in posts if post.get("id")}
    
    # Process in batches to avoid token limits
    for batch_start in range(0, len(posts), batch_size):
        batch_end = min(batch_start + batch_size, len(posts))
        batch = posts[batch_start:batch_end]
        
        # Strip posts to minimal data for pre-scoring
        stripped_batch = [_strip_post_for_prescore(post) for post in batch]
        
        # Build compact summary of posts for batch analysis
        # Use json.dumps to ensure proper escaping for JSON context
        posts_summary_lines = []
        for idx, post in enumerate(stripped_batch):
            title = post.get("title", "")
            snippet = post.get("selftext", "")  # Already truncated to 750 chars
            posts_summary_lines.append(
                f"POST {idx}:\nTitle: {json.dumps(title)}\nContent: {json.dumps(snippet)}\n"
            )
        
        posts_summary = "\n".join(posts_summary_lines)
        
        prompt_context = {
            "segment_name": segment_name,
            "audience": segment_config.get("audience", ""),
            "priorities_list": "\n".join([f"• {p}" for p in segment_config.get("priorities", [])]),
            "posts_summary": posts_summary,
        }
        
        logger.info(
            "Starting batch pre-score (batch %d-%d)",
            batch_start,
            batch_end,
            extra={
                "operation": "batch_prescore",
                "segment_name": segment_name,
                "batch_start": batch_start,
                "batch_end": batch_end,
                "batch_size": len(batch),
            },
        )
        
        # Debug: Log what we're sending to Gemini
        logger.info(
            "Sending to Gemini - full posts_summary: %s",
            posts_summary,
            extra={
                "operation": "batch_prescore",
                "segment_name": segment_name,
                "batch_start": batch_start,
                "full_posts_summary_length": len(posts_summary),
            },
        )
        
        try:
            response = gemini_client.generate_json_response(
                "voc_reddit_batch_prescore.txt",
                prompt_context,
                temperature=0.3,
                max_output_tokens=4096,
            )
            
            # Debug: Log what we got back from Gemini (before parsing)
            logger.info(
                "Received from Gemini - full raw response: %s",
                response.raw_text if response and response.raw_text else "EMPTY",
                extra={
                    "operation": "batch_prescore",
                    "segment_name": segment_name,
                    "batch_start": batch_start,
                    "full_response_length": len(response.raw_text) if response and response.raw_text else 0,
                },
            )
        except GeminiClientError as exc:
            # Log the error WITH the raw response if available
            logger.error(
                "Gemini API or parsing error: %s",
                str(exc),
                extra={
                    "operation": "batch_prescore",
                    "segment_name": segment_name,
                    "batch_start": batch_start,
                },
            )
            warning = f"Batch pre-score failed for posts {batch_start}-{batch_end}: {exc}"
            warnings.append(warning)
            continue
        
        if not response or not response.data:
            warning = f"Batch pre-score returned empty response for posts {batch_start}-{batch_end}"
            logger.warning(warning, extra={"operation": "batch_prescore", "segment_name": segment_name})
            warnings.append(warning)
            continue
        
        if not isinstance(response.data, list):
            warning = f"Batch pre-score returned unexpected format for posts {batch_start}-{batch_end}"
            logger.warning(warning, extra={"operation": "batch_prescore", "segment_name": segment_name})
            warnings.append(warning)
            continue
        
        # Merge scores back into ORIGINAL full posts (not stripped versions)
        for score_obj in response.data:
            idx = score_obj.get("post_index")
            if idx is None or idx >= len(batch):
                continue
            
            # Get the original post ID from the stripped batch
            stripped_post = stripped_batch[idx]
            post_id = stripped_post.get("id")
            
            # Retrieve the full original post from memory
            original_post = posts_by_id.get(post_id)
            if not original_post:
                continue
            
            # Add prescore to the original full post
            enriched_post = original_post.copy()
            enriched_post["prescore"] = {
                "relevance_score": score_obj.get("relevance_score", 0),
                "quick_reason": score_obj.get("quick_reason", ""),
            }
            all_scored_posts.append(enriched_post)
        
        logger.info(
            "Batch pre-score complete for posts %d-%d",
            batch_start,
            batch_end,
            extra={
                "operation": "batch_prescore",
                "segment_name": segment_name,
                "scored_count": len(response.data),
            },
        )
    
    logger.info(
        "All batches complete",
        extra={
            "operation": "batch_prescore",
            "segment_name": segment_name,
            "total_scored": len(all_scored_posts),
            "total_input": len(posts),
        },
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


__all__ = ["filter_high_value_posts", "generate_curated_queries"]

