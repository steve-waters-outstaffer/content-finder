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
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import requests
from google.cloud import firestore
from pytrends.request import TrendReq

logger = logging.getLogger(__name__)

SCRAPECREATORS_SUBREDDIT_URL = "https://api.scrapecreators.com/v1/reddit/subreddit"
FIRESTORE_COLLECTION = "voc_discovery_processed_posts"

_firestore_client: Optional[firestore.Client] = None
_firestore_initialized = False
_local_dedupe_cache: Dict[str, set[str]] = {}


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
    reddit_api_key: Optional[str],
) -> Dict[str, Any]:
    """Execute the discovery workflow for a given segment."""

    segment_config = _load_segment_config(segment_name)

    reddit_posts: List[Dict[str, Any]] = []
    google_trends: List[Dict[str, Any]] = []
    warnings: List[str] = []

    try:
        reddit_posts, reddit_warnings = fetch_reddit_posts(segment_config, reddit_api_key, segment_name)
        warnings.extend(reddit_warnings)
    except Exception as exc:  # noqa: BLE001 - capture any fatal reddit issues
        warning = f"Reddit discovery failed: {exc}"
        logger.error(warning)
        warnings.append(warning)

    try:
        google_trends, trends_warnings = fetch_google_trends(segment_config)
        warnings.extend(trends_warnings)
    except Exception as exc:  # noqa: BLE001 - capture any fatal trends issues
        warning = f"Google Trends discovery failed: {exc}"
        logger.error(warning)
        warnings.append(warning)

    return {
        "reddit_posts": reddit_posts,
        "google_trends": google_trends,
        "curated_queries": [],
        "warnings": warnings,
    }

