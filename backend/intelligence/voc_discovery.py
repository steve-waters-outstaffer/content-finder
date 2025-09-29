"""Utilities for the Voice of Customer discovery workflow (Phase 1).

This module currently supports fetching high-signal Reddit posts and
enriching research with complementary Google Trends data. Later phases will
extend this module with AI-based scoring and synthesis, but the initial
version focuses on deterministic data gathering so the new API endpoint can
return actionable results immediately.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import requests
from google import genai
from google.genai import types
from google.cloud import firestore
from pytrends.request import TrendReq

logger = logging.getLogger(__name__)

SCRAPECREATORS_SUBREDDIT_URL = "https://api.scrapecreators.com/v1/reddit/subreddit"
SCRAPECREATORS_COMMENTS_URL = "https://api.scrapecreators.com/v1/reddit/post/comments"
FIRESTORE_COLLECTION = "voc_discovery_processed_posts"
DEFAULT_GEMINI_MODEL = os.getenv("MODEL", "gemini-2.5-flash")
ADVANCED_GEMINI_MODEL = os.getenv("MODEL_PRO", DEFAULT_GEMINI_MODEL)

_firestore_client: Optional[firestore.Client] = None
_firestore_initialized = False
_local_dedupe_cache: Dict[str, set[str]] = {}
_gemini_client: Optional[genai.Client] = None


class VOCDiscoveryError(RuntimeError):
    """Raised when the discovery workflow encounters a fatal error."""


@dataclass
class RedditFilters:
    """Typed structure for Reddit filtering rules."""

    min_score: int = 0
    min_comments: int = 0
    time_range: str = "month"
    sort: str = "top"


def _get_firestore_client() -> Optional[firestore.Client]:
    """Return a Firestore client if credentials are configured."""

    global _firestore_client, _firestore_initialized
    if _firestore_initialized:
        return _firestore_client

    _firestore_initialized = True
    try:
        _firestore_client = firestore.Client()
    except Exception as exc:  # noqa: BLE001 - log-and-fallback for optional dependency
        logger.warning("Firestore client unavailable, falling back to in-memory dedupe: %s", exc)
        _firestore_client = None

    return _firestore_client


def _get_local_cache(segment_name: str) -> set[str]:
    """Retrieve (or initialise) the in-memory dedupe cache for a segment."""

    if segment_name not in _local_dedupe_cache:
        _local_dedupe_cache[segment_name] = set()
    return _local_dedupe_cache[segment_name]


def _get_gemini_client() -> Optional[genai.Client]:
    """Return a Gemini client when credentials are available."""

    global _gemini_client
    if _gemini_client is not None:
        return _gemini_client

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    _gemini_client = genai.Client(api_key=api_key)
    return _gemini_client


def _load_segment_config(segment_name: str) -> Dict[str, Any]:
    """Load the JSON configuration associated with a given segment."""

    slug = segment_name.strip().lower().replace(" ", "_")
    config_path = (
        Path(__file__).resolve().parent
        / "config"
        / "prompts"
        / f"segment_{slug}.json"
    )

    if not config_path.exists():
        raise VOCDiscoveryError(f"No configuration found for segment '{segment_name}'.")

    with config_path.open("r", encoding="utf-8") as config_file:
        try:
            return json.load(config_file)
        except json.JSONDecodeError as exc:  # noqa: BLE001 - configuration needs surfacing
            raise VOCDiscoveryError(
                f"Configuration file for segment '{segment_name}' is invalid JSON: {exc}."
            ) from exc


def _parse_filters(config: Dict[str, Any]) -> RedditFilters:
    """Extract Reddit filter settings from a segment configuration."""

    filters = config.get("reddit_filters", {})
    return RedditFilters(
        min_score=int(filters.get("min_score", 0)),
        min_comments=int(filters.get("min_comments", 0)),
        time_range=str(filters.get("time_range", "month")),
        sort=str(filters.get("sort", "top")),
    )


def _load_processed_post_ids(segment_name: str) -> set[str]:
    """Fetch the set of Reddit post IDs already processed for a segment."""

    firestore_client = _get_firestore_client()
    if not firestore_client:
        return set(_get_local_cache(segment_name))

    collection_ref = firestore_client.collection(FIRESTORE_COLLECTION)
    segment_ref = collection_ref.document(segment_name).collection("posts")

    processed_ids: set[str] = set()
    try:
        for doc in segment_ref.stream():  # type: ignore[attr-defined]
            processed_ids.add(doc.id)
    except Exception as exc:  # noqa: BLE001 - fallback to in-memory cache
        logger.warning("Failed to load Firestore history for '%s': %s", segment_name, exc)
        return set(_get_local_cache(segment_name))

    _local_dedupe_cache[segment_name] = processed_ids
    return processed_ids


def _mark_posts_processed(segment_name: str, post_ids: Iterable[str]) -> None:
    """Persist the processed post IDs to Firestore (with in-memory fallback)."""

    ids_to_store = {post_id for post_id in post_ids if post_id}
    if not ids_to_store:
        return

    firestore_client = _get_firestore_client()
    if firestore_client:
        batch = firestore_client.batch()
        segment_collection = firestore_client.collection(FIRESTORE_COLLECTION).document(segment_name).collection("posts")

        timestamp = datetime.utcnow().isoformat()
        for post_id in ids_to_store:
            doc_ref = segment_collection.document(post_id)
            batch.set(doc_ref, {"processed_at": timestamp})

        try:
            batch.commit()
        except Exception as exc:  # noqa: BLE001 - ensure we still update in-memory cache
            logger.warning("Failed to persist Reddit post history to Firestore: %s", exc)

    cache = _get_local_cache(segment_name)
    cache.update(ids_to_store)


def fetch_reddit_posts(
    segment_config: Dict[str, Any],
    api_key: Optional[str],
    segment_name: str,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Fetch high-signal Reddit posts for a segment.

    Returns a tuple of (posts, warnings).
    """

    subreddits: Sequence[str] = segment_config.get("subreddits", [])
    if not subreddits:
        return [], ["Segment configuration does not define any subreddits to monitor."]

    if not api_key:
        raise VOCDiscoveryError("SCRAPECREATORS_API_KEY is required to fetch Reddit posts.")

    filters = _parse_filters(segment_config)
    processed_ids = _load_processed_post_ids(segment_name)

    headers = {"x-api-key": api_key}
    warnings: List[str] = []
    curated_posts: List[Dict[str, Any]] = []

    for subreddit in subreddits:
        params = {
            "subreddit": subreddit,
            "timeframe": filters.time_range,
            "sort": filters.sort,
        }

        try:
            response = requests.get(
                SCRAPECREATORS_SUBREDDIT_URL,
                headers=headers,
                params=params,
                timeout=30,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            warning = f"Failed to fetch subreddit '{subreddit}': {exc}"
            logger.warning(warning)
            warnings.append(warning)
            continue

        payload = response.json() if response.content else {}
        raw_posts: Sequence[Dict[str, Any]] = []

        if isinstance(payload, dict):
            if "data" in payload and isinstance(payload["data"], list):
                raw_posts = payload["data"]
            elif "posts" in payload and isinstance(payload["posts"], list):
                raw_posts = payload["posts"]
            elif "data" in payload and isinstance(payload["data"], dict) and "children" in payload["data"]:
                raw_posts = [child.get("data", {}) for child in payload["data"].get("children", [])]
        elif isinstance(payload, list):
            raw_posts = payload

        for post in raw_posts:
            post_id = str(post.get("id", "")).strip()
            if not post_id or post_id in processed_ids:
                continue

            score = int(post.get("ups") or post.get("score") or 0)
            comment_count = int(post.get("num_comments") or 0)

            if score < filters.min_score or comment_count < filters.min_comments:
                continue

            curated_posts.append(
                {
                    "id": post_id,
                    "title": post.get("title", ""),
                    "subreddit": post.get("subreddit", subreddit),
                    "score": score,
                    "num_comments": comment_count,
                    "url": post.get("url") or post.get("full_link"),
                    "content_snippet": (post.get("selftext") or "")[:300],
                }
            )

    _mark_posts_processed(segment_name, (post["id"] for post in curated_posts))
    return curated_posts, warnings


def _load_prompt_template(filename: str) -> str:
    """Load a prompt template from the prompts directory."""

    prompt_path = Path(__file__).resolve().parent / "config" / "prompts" / filename
    if not prompt_path.exists():
        raise VOCDiscoveryError(f"Prompt template '{filename}' is missing.")
    return prompt_path.read_text(encoding="utf-8")


def _extract_post_body(payload: Any) -> str:
    """Attempt to locate the original post body within a comments payload."""

    if isinstance(payload, dict):
        if isinstance(payload.get("selftext"), str) and payload.get("selftext"):  # type: ignore[redundant-expr]
            return payload["selftext"]  # type: ignore[index]
        data = payload.get("data")
        if data:
            body = _extract_post_body(data)
            if body:
                return body
        for value in payload.values():
            if isinstance(value, (dict, list)):
                body = _extract_post_body(value)
                if body:
                    return body
    elif isinstance(payload, list):
        for item in payload:
            body = _extract_post_body(item)
            if body:
                return body
    return ""


def _extract_comment_bodies(payload: Any, limit: int = 5) -> List[str]:
    """Collect up to `limit` human-written comment bodies from a payload."""

    comments: List[str] = []

    def _visit(node: Any) -> None:
        if len(comments) >= limit:
            return
        if isinstance(node, dict):
            body = node.get("body")
            if isinstance(body, str):
                trimmed = body.strip()
                if trimmed and trimmed.lower() not in {"[deleted]", "[removed]"}:
                    comments.append(trimmed)
                    if len(comments) >= limit:
                        return
            for key in ("replies", "data", "children"):
                value = node.get(key)
                if isinstance(value, (dict, list)):
                    _visit(value)
        elif isinstance(node, list):
            for item in node:
                if len(comments) >= limit:
                    break
                _visit(item)

    _visit(payload)
    return comments[:limit]


def _normalise_json_response(response_text: str) -> Any:
    """Better JSON parsing with error recovery"""

    if not response_text:
        raise ValueError("Empty response from Gemini")

    try:
        # Try to parse as-is
        return json.loads(response_text)
    except json.JSONDecodeError as exc:
        logger.warning("Initial JSON parse failed: %s", exc)

        # Try to extract JSON from markdown code blocks
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response_text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try to find first complete JSON object
        try:
            start = response_text.index("{")
            end = response_text.rindex("}") + 1
            potential_json = response_text[start:end]
            return json.loads(potential_json)
        except (ValueError, json.JSONDecodeError):
            pass

        # Last resort - try to fix common issues
        cleaned = response_text.strip().replace("\n", " ").replace("\\n", "\\\\n")
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as final_exc:
            raise ValueError(
                f"Could not parse JSON after multiple attempts: {response_text[:200]}"
            ) from final_exc


def get_post_details_and_score(
    post: Dict[str, Any],
    segment_config: Dict[str, Any],
    api_key: Optional[str],
    *,
    segment_name: str,
) -> Tuple[Dict[str, Any], List[str]]:
    """Enrich a Reddit post with discussion context and AI relevance scoring."""

    enriched_post = dict(post)
    warnings: List[str] = []

    if not api_key:
        warnings.append("SCRAPECREATORS_API_KEY missing; skipped Reddit comment enrichment.")
        return enriched_post, warnings

    headers = {"x-api-key": api_key}
    params = {"url": enriched_post.get("url")}

    comments_payload: Any = {}
    if params["url"]:
        try:
            response = requests.get(
                SCRAPECREATORS_COMMENTS_URL,
                headers=headers,
                params=params,
                timeout=30,
            )
            response.raise_for_status()
            comments_payload = response.json() if response.content else {}
        except requests.RequestException as exc:
            warning = f"Failed to fetch comments for post '{enriched_post.get('id')}': {exc}"
            logger.warning(warning)
            warnings.append(warning)

    post_body = enriched_post.get("content_snippet", "")
    if comments_payload:
        extracted_body = _extract_post_body(comments_payload)
        if extracted_body:
            post_body = extracted_body
    comment_bodies = _extract_comment_bodies(comments_payload) if comments_payload else []

    discussion_lines = [f"Title: {enriched_post.get('title', '')}"]
    if post_body:
        discussion_lines.append("\nPost Body:\n" + post_body.strip())
    if comment_bodies:
        formatted_comments = "\n---\n".join(comment_bodies)
        discussion_lines.append("\nTop Comments:\n" + formatted_comments)
    discussion_text = "\n\n".join(discussion_lines)

    gemini_client = _get_gemini_client()
    if not gemini_client:
        warnings.append("GEMINI_API_KEY missing; skipped AI scoring for Reddit posts.")
        return enriched_post, warnings

    try:
        prompt_template = _load_prompt_template("voc_reddit_analysis_prompt.txt")
        prompt = prompt_template.format(
            segment_name=segment_name,
            audience=segment_config.get("audience", ""),
            subreddit=enriched_post.get("subreddit", ""),
            discussion_text=discussion_text,
        )
    except Exception as exc:
        warning = f"Failed to load Reddit analysis prompt: {exc}"
        logger.error(warning)
        warnings.append(warning)
        return enriched_post, warnings

    try:
        response = gemini_client.models.generate_content(
            model=ADVANCED_GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.2,
                max_output_tokens=1024,
            ),
        )
        parsed = _normalise_json_response(response.text or "")
        if isinstance(parsed, dict):
            enriched_post["ai_analysis"] = parsed
        else:
            warnings.append("Gemini returned unexpected structure for Reddit analysis.")
    except Exception as exc:  # noqa: BLE001 - capture parsing and API issues
        warning = f"Gemini Reddit analysis failed for post '{enriched_post.get('id')}': {exc}"
        logger.warning(warning)
        warnings.append(warning)

    return enriched_post, warnings


def generate_curated_queries(
    analyzed_posts: Sequence[Dict[str, Any]],
    trends_data: Sequence[Dict[str, Any]],
    segment_config: Dict[str, Any],
    *,
    segment_name: str,
) -> Tuple[List[str], List[str]]:
    """Synthesise the Reddit and Google Trends insights into research queries."""

    gemini_client = _get_gemini_client()
    if not gemini_client:
        return [], ["GEMINI_API_KEY missing; unable to generate curated queries."]

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
        rising = trend.get("related_queries", {}).get("rising", []) if isinstance(trend.get("related_queries"), dict) else []
        rising_terms = ", ".join(
            str(item.get("query"))
            for item in rising[:3]
            if isinstance(item, dict) and item.get("query")
        )
        if rising_terms:
            trends_lines.append(f"- {query}: rising searches include {rising_terms}")
        else:
            trends_lines.append(f"- {query}: steady interest over time")

    pain_points = "\n".join(pain_point_lines) if pain_point_lines else "- No AI-analyzed Reddit posts were available."
    trends_summary = "\n".join(trends_lines) if trends_lines else "- Google Trends data unavailable."

    try:
        prompt_template = _load_prompt_template("voc_curated_queries_prompt.txt")
        prompt = prompt_template.format(
            segment_name=segment_name,
            audience=segment_config.get("audience", ""),
            pain_points=pain_points,
            trends_summary=trends_summary,
        )
    except Exception as exc:
        warning = f"Failed to load curated queries prompt: {exc}"
        logger.error(warning)
        return [], [warning]

    try:
        response = gemini_client.models.generate_content(
            model=ADVANCED_GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.3,
                max_output_tokens=1024,
            ),
        )
        parsed = _normalise_json_response(response.text or "")
        if isinstance(parsed, list):
            cleaned_queries = [str(item).strip() for item in parsed if str(item).strip()]
            return cleaned_queries, []
        return [], ["Gemini returned unexpected structure for curated queries generation."]
    except Exception as exc:  # noqa: BLE001 - capture parsing and API issues
        warning = f"Gemini curated query generation failed: {exc}"
        logger.warning(warning)
        return [], [warning]


def _dataframe_to_records(dataframe: Any, *, rename_columns: Optional[Dict[str, str]] = None) -> List[Dict[str, Any]]:
    """Convert a pandas DataFrame to a list of JSON-serialisable records."""

    if dataframe is None or getattr(dataframe, "empty", True):
        return []

    working_df = dataframe
    if rename_columns:
        working_df = working_df.rename(columns=rename_columns)

    records: List[Dict[str, Any]] = []
    for record in working_df.reset_index().to_dict(orient="records"):
        serialised: Dict[str, Any] = {}
        for key, value in record.items():
            if hasattr(value, "isoformat"):
                serialised[key] = value.isoformat()
            else:
                serialised[key] = value
        records.append(serialised)
    return records


def _extract_related_queries(related_queries: Dict[str, Any], keyword: str) -> Dict[str, List[Dict[str, Any]]]:
    """Normalise the related queries response for a specific keyword."""

    keyword_data = related_queries.get(keyword, {}) if related_queries else {}
    return {
        "top": _dataframe_to_records(keyword_data.get("top")),
        "rising": _dataframe_to_records(keyword_data.get("rising")),
    }


def _extract_related_topics(related_topics: Dict[str, Any], keyword: str) -> Dict[str, List[Dict[str, Any]]]:
    """Normalise the related topics response for a specific keyword."""

    keyword_data = related_topics.get(keyword, {}) if related_topics else {}
    return {
        "top": _dataframe_to_records(keyword_data.get("top")),
        "rising": _dataframe_to_records(keyword_data.get("rising")),
    }


def fetch_google_trends(segment_config: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Fetch Google Trends data for each primary query in the configuration."""

    trends_config = segment_config.get("google_trends", {})
    primary_keywords: Sequence[str] = trends_config.get("primary_keywords") or segment_config.get("search_keywords", [])
    comparison_keyword: Optional[str] = trends_config.get("comparison_keyword")
    timeframe: str = trends_config.get("timeframe", "today 12-m")
    geo: str = trends_config.get("geo", "")

    if not primary_keywords:
        return [], ["No Google Trends keywords configured for this segment."]

    pytrends = TrendReq(hl="en-US", tz=360)
    curated_trends: List[Dict[str, Any]] = []
    warnings: List[str] = []

    for keyword in primary_keywords:
        query_terms = [keyword]
        if comparison_keyword and comparison_keyword.lower() != keyword.lower():
            query_terms.append(comparison_keyword)

        try:
            pytrends.build_payload(query_terms, timeframe=timeframe, geo=geo)
            interest_over_time = pytrends.interest_over_time()
            related_queries = pytrends.related_queries()
            related_topics = pytrends.related_topics()
        except Exception as exc:  # noqa: BLE001 - network/service level failures are non-fatal
            warning = f"Google Trends lookup failed for '{keyword}': {exc}"
            logger.warning(warning)
            warnings.append(warning)
            continue

        curated_trends.append(
            {
                "query": keyword,
                "comparison_keyword": comparison_keyword,
                "interest_over_time": _dataframe_to_records(
                    interest_over_time,
                    rename_columns={keyword: "primary_interest"},
                ),
                "related_queries": _extract_related_queries(related_queries, keyword),
                "related_topics": _extract_related_topics(related_topics, keyword),
            }
        )

    return curated_trends, warnings


def run_voc_discovery(
    segment_name: str,
    segment_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Enhanced VOC discovery with detailed logging."""

    warnings: List[str] = []
    results: Dict[str, Any] = {
        "segment": segment_name,
        "reddit_posts": [],
        "google_trends": [],
        "curated_queries": [],
        "warnings": warnings,
        "logs": [],
    }

    def log_progress(message: str, level: str = "info") -> None:
        log_method = getattr(logger, level, None)
        if not callable(log_method):
            log_method = logger.info
        log_method(message)
        results["logs"].append(
            {
                "timestamp": time.time(),
                "level": level,
                "message": message,
            }
        )

    log_progress(f"Initializing VOC Discovery for segment: {segment_name}")

    try:
        base_config = _load_segment_config(segment_name)
        log_progress("Loaded segment configuration")
    except VOCDiscoveryError:
        raise
    except Exception as exc:  # noqa: BLE001 - escalate unexpected configuration failures
        error_msg = f"Failed to load configuration for segment '{segment_name}': {exc}"
        log_progress(error_msg, "error")
        raise VOCDiscoveryError(error_msg) from exc

    if segment_config:
        merged_config: Dict[str, Any] = dict(base_config)
        for key, value in segment_config.items():
            if isinstance(value, dict) and isinstance(merged_config.get(key), dict):
                updated = dict(merged_config[key])
                updated.update(value)
                merged_config[key] = updated
            else:
                merged_config[key] = value
        segment_config = merged_config
    else:
        segment_config = base_config

    reddit_api_key = os.getenv("SCRAPECREATORS_API_KEY")
    fetched_reddit_posts: List[Dict[str, Any]] = []

    if segment_config.get("enable_reddit", True):
        subreddits = segment_config.get("subreddits", [])
        log_progress(f"Starting Reddit discovery for segment: {segment_name}")
        log_progress(f"Searching {len(subreddits)} subreddits: {', '.join(subreddits)}")

        if not reddit_api_key:
            warning = "SCRAPECREATORS_API_KEY missing; skipped Reddit discovery."
            log_progress(warning, "warning")
            warnings.append(warning)
        else:
            try:
                fetched_reddit_posts, reddit_warnings = fetch_reddit_posts(
                    segment_config,
                    reddit_api_key,
                    segment_name,
                )
                log_progress(
                    f"Found {len(fetched_reddit_posts)} Reddit posts for analysis", "success"
                )
                for warning_msg in reddit_warnings:
                    log_progress(warning_msg, "warning")
                    warnings.append(warning_msg)
            except Exception as exc:  # noqa: BLE001 - capture fetch-level errors
                error_msg = f"Failed to fetch Reddit posts: {exc}"
                log_progress(error_msg, "error")
                warnings.append(error_msg)

            for post in fetched_reddit_posts:
                try:
                    log_progress(
                        f"Analyzing post '{post.get('title', 'Untitled')[:50]}...'"
                    )
                    enriched_post, post_warnings = get_post_details_and_score(
                        post,
                        segment_config,
                        reddit_api_key,
                        segment_name=segment_name,
                    )
                    if enriched_post:
                        results["reddit_posts"].append(enriched_post)
                        log_progress(
                            f"✓ Successfully analyzed post {enriched_post.get('id')}", "success"
                        )
                    for warning_msg in post_warnings:
                        log_progress(warning_msg, "warning")
                        warnings.append(warning_msg)
                except Exception as exc:  # noqa: BLE001 - capture enrichment errors per post
                    error_msg = f"Failed to analyze post {post.get('id')}: {exc}"
                    log_progress(error_msg, "error")
                    warnings.append(error_msg)
    else:
        log_progress("Reddit discovery disabled in configuration", "warning")

    if segment_config.get("enable_trends", True):
        log_progress("Starting Google Trends analysis...")
        trends_config = (
            segment_config.get("google_trends")
            if isinstance(segment_config.get("google_trends"), dict)
            else {}
        )
        trends_keywords: Sequence[str] = (
            segment_config.get("trends_keywords")
            or trends_config.get("primary_keywords")
            or segment_config.get("search_keywords", [])
        )

        log_progress(
            f"Analyzing {len(trends_keywords)} keywords: {', '.join(map(str, trends_keywords))}"
        )

        if not trends_keywords:
            warning = "No Google Trends keywords configured for this segment."
            log_progress(warning, "warning")
            warnings.append(warning)
        else:
            for keyword in trends_keywords:
                try:
                    log_progress(f"Fetching trends for '{keyword}'...")
                    time.sleep(2)

                    single_segment_config = dict(segment_config)
                    single_trends_config = dict(trends_config)
                    single_trends_config["primary_keywords"] = [keyword]
                    single_segment_config["google_trends"] = single_trends_config

                    trend_results, trend_warnings = fetch_google_trends(single_segment_config)
                    for warning_msg in trend_warnings:
                        log_progress(warning_msg, "warning")
                        warnings.append(warning_msg)
                    if trend_results:
                        results["google_trends"].extend(trend_results)
                        log_progress(f"✓ Got trends data for '{keyword}'", "success")
                except Exception as exc:  # noqa: BLE001 - handle per-keyword failures
                    if "429" in str(exc):
                        log_progress(
                            f"Rate limited on '{keyword}', waiting 10 seconds...",
                            "warning",
                        )
                        time.sleep(10)
                    else:
                        error_msg = f"Trends failed for '{keyword}': {exc}"
                        log_progress(error_msg, "error")
                        warnings.append(error_msg)
    else:
        log_progress("Google Trends analysis disabled in configuration", "warning")

    if segment_config.get("enable_curated_queries", True):
        log_progress("Generating AI-curated search queries...")
        try:
            curated_queries, query_warnings = generate_curated_queries(
                results["reddit_posts"] or fetched_reddit_posts,
                results["google_trends"],
                segment_config,
                segment_name=segment_name,
            )
            results["curated_queries"] = curated_queries
            log_progress(
                f"✓ Generated {len(curated_queries)} curated queries", "success"
            )
            for warning_msg in query_warnings:
                log_progress(warning_msg, "warning")
                warnings.append(warning_msg)
        except Exception as exc:  # noqa: BLE001 - capture synthesis failures
            error_msg = f"Failed to generate curated queries: {exc}"
            log_progress(error_msg, "error")
            warnings.append(error_msg)
    else:
        log_progress("Curated queries generation disabled in configuration", "warning")

    log_progress(
        "Discovery complete! Found "
        f"{len(results['reddit_posts'])} Reddit posts, {len(results['google_trends'])} trends signals",
        "success",
    )

    return results

