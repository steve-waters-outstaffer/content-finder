"""AI synthesis helpers for VOC discovery."""

from __future__ import annotations

import html
import json
import logging
import time
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Sequence, Tuple

from core.gemini_client import GeminiClient, GeminiClientError
from intelligence.models import (
    PRESCORE_RESPONSE_SCHEMA,
    PreScoreResult,
)
from pydantic import ValidationError

logger = logging.getLogger(__name__)


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


def pre_score_post(
    post: Dict[str, Any],
    segment_name: str,
    *,
    gemini_client: GeminiClient,
    segment_config: Optional[Dict[str, Any]] = None,
) -> PreScoreResult:
    """Run Gemini pre-scoring for a single Reddit post."""

    segment_config = segment_config or {}
    stripped_post = _strip_post_for_prescore(post)

    context = {
        "segment_name": segment_name,
        "audience": segment_config.get("audience", ""),
        "priorities": "\n".join(
            f"• {priority}" for priority in segment_config.get("priorities", [])
        )
        or "(no explicit priorities provided)",
        "post_id": stripped_post.get("id", ""),
        "post_title": stripped_post.get("title", ""),
        "post_snippet": stripped_post.get("content", ""),
        "subreddit": stripped_post.get("subreddit", ""),
    }

    request_payload = {
        "template_name": "voc_reddit_prescore_prompt.txt",
        "context": context,
        "model": gemini_client.default_model,
        "temperature": 0.0,
        "max_output_tokens": 2048,
        "response_schema": deepcopy(PRESCORE_RESPONSE_SCHEMA),
    }
    logger.info(
        "Gemini pre-score request",
        extra={
            "operation": "pre_score_post",
            "segment_name": segment_name,
            "post_id": stripped_post.get("id", ""),
            "post_title": stripped_post.get("title", "")[:100],
            "post_snippet": stripped_post.get("content", "")[:200],
            "model": gemini_client.default_model,
            "prompt_context": context,
            "audience": segment_config.get("audience", ""),
            "priorities": segment_config.get("priorities", []),
        },
    )

    try:
        response = gemini_client.generate_json_response(
            template_name="voc_reddit_prescore_prompt.txt",
            context=context,
            model=gemini_client.default_model,
            temperature=0.0,
            max_output_tokens=2048,
            response_schema=PRESCORE_RESPONSE_SCHEMA,
        )
        
        # Log the actual prompt that was sent (load template and render it)
        try:
            prompt_template = gemini_client._load_prompt("voc_reddit_prescore_prompt.txt")
            rendered_prompt = prompt_template.format(**context)
            logger.info(
                "Rendered prompt sent to Gemini",
                extra={
                    "operation": "pre_score_post",
                    "segment_name": segment_name,
                    "post_id": stripped_post.get("id", ""),
                    "rendered_prompt": rendered_prompt[:1000],  # First 1000 chars
                    "prompt_length": len(rendered_prompt),
                },
            )
        except Exception as prompt_log_exc:
            # Don't fail scoring if we can't log the prompt
            logger.debug(f"Could not log rendered prompt: {prompt_log_exc}")
            
    except GeminiClientError:
        raise
    except Exception as exc:  # noqa: BLE001 - surface unexpected errors consistently
        raise GeminiClientError(f"Gemini pre-score request failed: {exc}") from exc

    logger.info(
        "Gemini pre-score response received",
        extra={
            "operation": "pre_score_post",
            "segment_name": segment_name,
            "post_id": stripped_post.get("id", ""),
            "raw_response": response.raw_text[:500],
            "response_length": len(response.raw_text),
            "full_raw_response": response.raw_text,  # Include full response for debugging
            "expected_schema": PRESCORE_RESPONSE_SCHEMA,
        },
    )

    try:
        result = PreScoreResult(**response.data)
        logger.info(
            "Response parsed successfully",
            extra={
                "operation": "pre_score_post",
                "segment_name": segment_name,
                "post_id": stripped_post.get("id", ""),
                "parsed_data": response.data,
            },
        )
    except ValidationError as exc:  # noqa: BLE001 - validation errors should bubble up
        logger.warning(
            "Pre-score validation failed",
            extra={
                "operation": "pre_score_post",
                "segment_name": segment_name,
                "post_id": stripped_post.get("id", ""),
                "error": str(exc),
                "raw_response": response.raw_text[:500],
                "full_raw_response": response.raw_text,
                "response_data": response.data,
                "expected_schema": PRESCORE_RESPONSE_SCHEMA,
            },
        )
        raise GeminiClientError("Pre-score validation failed") from exc
    except Exception as exc:
        logger.exception(
            "Unexpected error during pre-score processing",
            extra={
                "operation": "pre_score_post",
                "segment_name": segment_name,
                "post_id": stripped_post.get("id", ""),
                "error": str(exc),
                "raw_response": response.raw_text[:500],
            },
        )
        raise

    logger.info(
        "Pre-score successful",
        extra={
            "operation": "pre_score_post",
            "segment_name": segment_name,
            "post_id": result.post_id,
            "score": result.score,
            "priority": result.priority,
            "reason": result.reason[:200] if result.reason else "",
        },
    )
    return result


def pre_score_posts(
    posts: Sequence[Dict[str, Any]],
    segment_name: str,
    *,
    gemini_client: GeminiClient,
    segment_config: Optional[Dict[str, Any]] = None,
    max_workers: int = 5,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Pre-score posts concurrently while collecting warnings."""

    segment_config = segment_config or {}
    warnings: List[str] = []

    if not posts:
        return [], warnings

    start_time = time.perf_counter()
    scored_posts: List[Dict[str, Any]] = []
    
    logger.info(
        "Starting parallel pre-score",
        extra={
            "operation": "pre_score",
            "segment_name": segment_name,
            "post_count": len(posts),
            "max_workers": max_workers,
        },
    )

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {
            executor.submit(
                pre_score_post,
                post,
                segment_name,
                gemini_client=gemini_client,
                segment_config=segment_config,
            ): (index, post)
            for index, post in enumerate(posts)
        }

        for future in as_completed(future_map):
            index, original_post = future_map[future]
            post_id = original_post.get("id") or original_post.get("post_id") or ""

            try:
                prescore_result = future.result()
            except GeminiClientError as exc:
                warning = (
                    f"Pre-score failed for post '{post_id}' in segment '{segment_name}': {exc}"
                )
                logger.warning(
                    warning,
                    extra={
                        "operation": "pre_score",
                        "segment_name": segment_name,
                        "post_id": post_id,
                        "error_type": "GeminiClientError",
                        "error": str(exc),
                    },
                )
                warnings.append(warning)
                continue
            except Exception as exc:  # noqa: BLE001 - capture unexpected issues per post
                warning = (
                    f"Unexpected error during pre-score for post '{post_id}' in segment '{segment_name}': {exc}"
                )
                logger.exception(
                    warning,
                    extra={
                        "operation": "pre_score",
                        "segment_name": segment_name,
                        "post_id": post_id,
                        "error_type": type(exc).__name__,
                    },
                )
                warnings.append(warning)
                continue

            enriched_post = original_post.copy()
            enriched_post["prescore"] = {
                "relevance_score": prescore_result.score,
                "priority": prescore_result.priority,
                "quick_reason": prescore_result.reason or "",
            }
            enriched_post["_prescore_index"] = index
            scored_posts.append(enriched_post)
            
            # Log each successful score as it completes
            logger.info(
                "Post scored",
                extra={
                    "operation": "pre_score",
                    "segment_name": segment_name,
                    "post_id": post_id,
                    "score": prescore_result.score,
                    "priority": prescore_result.priority,
                    "progress": f"{len(scored_posts)}/{len(posts)}",
                },
            )

    scored_posts.sort(key=lambda item: item.get("_prescore_index", 0))
    for post in scored_posts:
        post.pop("_prescore_index", None)

    duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
    
    # Calculate score distribution for visibility
    scores = [p.get("prescore", {}).get("relevance_score", 0) for p in scored_posts]
    score_distribution = {
        "min": min(scores) if scores else 0,
        "max": max(scores) if scores else 0,
        "avg": round(sum(scores) / len(scores), 2) if scores else 0,
    }
    
    logger.info(
        "Pre-score complete",
        extra={
            "operation": "pre_score",
            "segment_name": segment_name,
            "input_count": len(posts),
            "scored_count": len(scored_posts),
            "failed_count": len(warnings),
            "score_distribution": score_distribution,
            "duration_ms": duration_ms,
        },
    )

    return scored_posts, warnings


def batch_prescore_posts(
    posts: Sequence[Dict[str, Any]],
    segment_config: Dict[str, Any],
    segment_name: str,
    gemini_client: GeminiClient,
    batch_size: int = 25,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Stage 1: Batch pre-score posts using only title + snippet (no comments).
    Fast, lightweight analysis to filter down to promising posts.
    
    Uses JSON array format for cleaner, more reliable Gemini parsing.
    Falls back to text format if payload exceeds token limits.
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
        
        # Build JSONL-style text input (one post per line, not a JSON array)
        # Each line contains post_index, title, and content for easy parsing
        posts_text_lines = []
        for i, post in enumerate(stripped_batch):
            post_line = {
                "post_index": i,
                "title": post.get("title", "[N/A]"),
                "content": post.get("content", "")
            }
            posts_text_lines.append(json.dumps(post_line, ensure_ascii=False))
        
        posts_summary = "\n".join(posts_text_lines)
        
        logger.info(
            "Using JSONL input format for Gemini (one post per line)",
            extra={
                "operation": "batch_prescore",
                "segment_name": segment_name,
                "batch_start": batch_start,
                "post_count": len(posts_text_lines),
            },
        )
        
        prompt_context = {
            "segment_name": segment_name,
            "audience": segment_config.get("audience", ""),
            "priorities_list": "\n".join([f"• {p}" for p in segment_config.get("priorities", [])]),
            "posts_json": posts_summary,
            "batch_size": len(batch),
        }
        
        logger.info(
            "Sending to Gemini - full posts_summary: %s",
            posts_summary[:500] + "..." if len(posts_summary) > 500 else posts_summary,
            extra={
                "operation": "batch_prescore",
                "segment_name": segment_name,
                "batch_start": batch_start,
                "full_posts_summary_length": len(posts_summary),
            },
        )
        
        try:
            # Use generate_text instead of generate_json_response since we're getting JSONL back
            # Gemini's JSON parser tries to parse the whole thing as one object, which fails with JSONL
            raw_text = gemini_client.generate_text(
                prompt=gemini_client._load_prompt("voc_reddit_batch_prescore.txt").format(**prompt_context),
                temperature=0.3,
                max_output_tokens=4096,
                response_mime_type="text/plain",  # Get plain text, we'll parse JSONL ourselves
            )
            
            # Create a response-like object for consistency with existing code
            class SimpleResponse:
                def __init__(self, text):
                    self.raw_text = text
            
            response = SimpleResponse(raw_text)
            
            # Debug: Log what we got back from Gemini (truncated)
            raw_text = response.raw_text if response and response.raw_text else "EMPTY"
            logger.info(
                "Received from Gemini - full raw response: %s",
                raw_text[:500] + "..." if len(raw_text) > 500 else raw_text,
                extra={
                    "operation": "batch_prescore",
                    "segment_name": segment_name,
                    "batch_start": batch_start,
                    "full_response_length": len(raw_text),
                },
            )
        except GeminiClientError as exc:
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
        
        if not response or not response.raw_text:
            warning = f"Batch pre-score returned empty response for posts {batch_start}-{batch_end}"
            logger.warning(warning, extra={"operation": "batch_prescore", "segment_name": segment_name})
            warnings.append(warning)
            continue
        
        # Parse JSONL format: one JSON object per line
        parsed_scores = []
        raw_lines = response.raw_text.strip().split('\n')
        
        logger.info(
            "Parsing JSONL response: %d lines",
            len(raw_lines),
            extra={
                "operation": "batch_prescore",
                "segment_name": segment_name,
                "batch_start": batch_start,
                "line_count": len(raw_lines),
            },
        )
        
        for line_num, line in enumerate(raw_lines, start=1):
            line = line.strip()
            if not line:
                continue  # Skip empty lines
            
            try:
                score_obj = json.loads(line)
                parsed_scores.append(score_obj)
                logger.debug(
                    "Successfully parsed JSONL line %d",
                    line_num,
                    extra={
                        "operation": "batch_prescore",
                        "segment_name": segment_name,
                        "line_num": line_num,
                        "post_index": score_obj.get("post_index"),
                    },
                )
            except json.JSONDecodeError as exc:
                # Log warning but continue processing other lines
                warning = f"Failed to parse JSONL line {line_num} in batch {batch_start}-{batch_end}: {exc} | Line: {line[:100]}"
                logger.warning(
                    warning,
                    extra={
                        "operation": "batch_prescore",
                        "segment_name": segment_name,
                        "batch_start": batch_start,
                        "line_num": line_num,
                    },
                )
                warnings.append(warning)
                continue  # Skip this line and move to the next
        
        if not parsed_scores:
            warning = f"No valid JSONL lines parsed for batch {batch_start}-{batch_end}"
            logger.warning(warning, extra={"operation": "batch_prescore", "segment_name": segment_name})
            warnings.append(warning)
            continue
        
        logger.info(
            "Successfully parsed %d/%d JSONL lines",
            len(parsed_scores),
            len(raw_lines),
            extra={
                "operation": "batch_prescore",
                "segment_name": segment_name,
                "batch_start": batch_start,
                "success_count": len(parsed_scores),
                "total_lines": len(raw_lines),
            },
        )
        
        # Merge scores back into ORIGINAL full posts (not stripped versions)
        for score_obj in parsed_scores:
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
                "relevance_score": score_obj.get("score", 0),  # Changed from relevance_score to score
                "quick_reason": score_obj.get("reason", ""),   # Changed from quick_reason to reason
            }
            all_scored_posts.append(enriched_post)
        
        logger.info(
            "Batch pre-score complete for posts %d-%d",
            batch_start,
            batch_end,
            extra={
                "operation": "batch_prescore",
                "segment_name": segment_name,
                "scored_count": len(parsed_scores),
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
