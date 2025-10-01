"""Reddit-specific helpers for the VOC discovery workflow."""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import requests
from google.cloud import firestore

from core.gemini_client import GeminiClient, GeminiClientError

logger = logging.getLogger(__name__)

SCRAPECREATORS_SUBREDDIT_URL = "https://api.scrapecreators.com/v1/reddit/subreddit"
SCRAPECREATORS_COMMENTS_URL = "https://api.scrapecreators.com/v1/reddit/post/comments"
FIRESTORE_COLLECTION = "voc_discovery_processed_posts"


@dataclass(slots=True)
class RedditFilters:
    min_score: int = 0
    min_comments: int = 0
    time_range: str = "month"
    sort: str = "top"


class RedditHistoryStore:
    """Handles Firestore + in-memory history for processed posts."""

    def __init__(self, client: Optional[firestore.Client] = None) -> None:
        self.client = client
        self._cache: Dict[str, set[str]] = {}

    @classmethod
    def create(cls) -> "RedditHistoryStore":
        try:
            client = firestore.Client()
            logger.debug(
                "Initialized Firestore client for history store",
                extra={"operation": "reddit_history_init"},
            )
        except Exception as exc:  # noqa: BLE001 - optional dependency
            logger.warning(
                "Firestore unavailable for VOC history: %s",
                exc,
                extra={"operation": "reddit_history_init"},
            )
            client = None
        return cls(client)

    def load(self, segment_name: str) -> set[str]:
        if segment_name in self._cache:
            return set(self._cache[segment_name])

        if not self.client:
            self._cache.setdefault(segment_name, set())
            return set()

        collection = (
            self.client.collection(FIRESTORE_COLLECTION)
            .document(segment_name)
            .collection("posts")
        )

        processed: set[str] = set()
        try:
            for doc in collection.stream():  # type: ignore[attr-defined]
                processed.add(doc.id)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to load Firestore history for '%s': %s",
                segment_name,
                exc,
                extra={"operation": "reddit_history_load", "segment_name": segment_name},
            )
            processed = set()

        self._cache[segment_name] = processed
        return set(processed)

    def mark(self, segment_name: str, post_ids: Iterable[str]) -> None:
        ids = {pid for pid in post_ids if pid}
        if not ids:
            return

        cache = self._cache.setdefault(segment_name, set())
        cache.update(ids)

        if not self.client:
            return

        batch = self.client.batch()
        segment_collection = (
            self.client.collection(FIRESTORE_COLLECTION)
            .document(segment_name)
            .collection("posts")
        )
        timestamp = datetime.utcnow().isoformat()
        for pid in ids:
            batch.set(segment_collection.document(pid), {"processed_at": timestamp})

        try:
            batch.commit()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "Failed to persist Reddit history: %s",
                exc,
                extra={"operation": "reddit_history_persist", "segment_name": segment_name},
            )


class RedditDataCollector:
    """Collects and enriches Reddit data for VOC discovery."""

    def __init__(
        self,
        *,
        api_key: str,
        gemini_client: GeminiClient,
        history_store: Optional[RedditHistoryStore] = None,
        prompt_dir: Optional[Path | str] = None,
    ) -> None:
        if not api_key:
            raise ValueError("SCRAPECREATORS_API_KEY is required to fetch Reddit data.")

        self.api_key = api_key
        self.gemini = gemini_client
        self.history_store = history_store or RedditHistoryStore.create()
        self.prompt_dir = Path(
            prompt_dir or Path(__file__).resolve().parent / "config" / "prompts"
        )
        self.advanced_model = os.environ.get("MODEL_PRO", self.gemini.default_model)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_filters(config: Dict[str, Any]) -> RedditFilters:
        filters = config.get("reddit_filters", {})
        return RedditFilters(
            min_score=int(filters.get("min_score", 0)),
            min_comments=int(filters.get("min_comments", 0)),
            time_range=str(filters.get("time_range", "month")),
            sort=str(filters.get("sort", "top")),
        )

    def _fetch_subreddit(
        self,
        subreddit: str,
        *,
        filters: RedditFilters,
    ) -> Sequence[Dict[str, Any]]:
        headers = {"x-api-key": self.api_key}
        params = {"subreddit": subreddit, "timeframe": filters.time_range, "sort": filters.sort}

        logger.info(
            f"Fetching posts from r/{subreddit} with filters: {filters}",
            extra={
                "operation": "reddit_fetch",
                "subreddit": subreddit,
                "filters": params,
            },
        )
        start_time = time.perf_counter()
        response = requests.get(
            SCRAPECREATORS_SUBREDDIT_URL,
            headers=headers,
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        payload = response.json() if response.content else {}
        if isinstance(payload, dict):
            if isinstance(payload.get("data"), list):
                posts = payload["data"]
                logger.info(
                    "API returned %s posts from r/%s",
                    len(posts),
                    subreddit,
                    extra={
                        "operation": "reddit_fetch",
                        "subreddit": subreddit,
                        "duration_ms": duration_ms,
                    },
                )
                logger.debug(
                    "Sample post IDs: %s",
                    [p.get("id") for p in posts[:3]],
                    extra={
                        "operation": "reddit_fetch",
                        "subreddit": subreddit,
                    },
                )
                return posts
            if isinstance(payload.get("posts"), list):
                posts = payload["posts"]
                logger.info(
                    "API returned %s posts from r/%s",
                    len(posts),
                    subreddit,
                    extra={
                        "operation": "reddit_fetch",
                        "subreddit": subreddit,
                        "duration_ms": duration_ms,
                    },
                )
                logger.debug(
                    "Sample post IDs: %s",
                    [p.get("id") for p in posts[:3]],
                    extra={
                        "operation": "reddit_fetch",
                        "subreddit": subreddit,
                    },
                )
                return posts
        logger.info(
            "API returned 0 posts from r/%s",
            subreddit,
            extra={
                "operation": "reddit_fetch",
                "subreddit": subreddit,
                "duration_ms": duration_ms,
            },
        )
        return []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def fetch_posts(
        self,
        *,
        segment_name: str,
        segment_config: Dict[str, Any],
        log_callback: Optional[callable] = None,
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        logger.info(
            "Starting Reddit fetch",
            extra={
                "operation": "reddit_fetch",
                "segment_name": segment_name,
            },
        )
        subreddits: Sequence[str] = segment_config.get("subreddits", [])
        if not subreddits:
            logger.warning(
                "No subreddits configured for segment",
                extra={
                    "operation": "reddit_fetch",
                    "segment_name": segment_name,
                },
            )
            return [], ["Segment configuration does not define any subreddits to monitor."]

        filters = self._parse_filters(segment_config)
        logger.debug(
            "Reddit filters resolved",
            extra={
                "operation": "reddit_fetch",
                "segment_name": segment_name,
                "filters": asdict(filters),
            },
        )
        processed_ids = self.history_store.load(segment_name)

        curated: List[Dict[str, Any]] = []
        warnings: List[str] = []

        def log(message: str, level: str = "info") -> None:
            if log_callback:
                log_callback(message, level)

        for subreddit in subreddits:
            try:
                posts = self._fetch_subreddit(subreddit, filters=filters)
            except requests.RequestException as exc:
                warning = f"Failed to fetch subreddit '{subreddit}': {exc}"
                logger.warning(
                    warning,
                    extra={
                        "operation": "reddit_fetch",
                        "segment_name": segment_name,
                        "subreddit": subreddit,
                    },
                )
                warnings.append(warning)
                log(f"r/{subreddit}: API fetch failed - {exc}", "error")
                continue

            log(f"Fetched {len(posts)} posts from r/{subreddit}")
            for post in posts:
                post_id = str(post.get("id") or post.get("post_id") or "")
                if not post_id or post_id in processed_ids:
                    continue
                if int(post.get("score", 0)) < filters.min_score:
                    logger.debug(
                        "Post %s: score=%s, min_score=%s, filtered=True",
                        post_id,
                        post.get("score"),
                        filters.min_score,
                        extra={
                            "operation": "reddit_filter",
                            "segment_name": segment_name,
                            "subreddit": subreddit,
                            "post_id": post_id,
                        },
                    )
                    continue
                if int(post.get("num_comments", 0)) < filters.min_comments:
                    logger.debug(
                        "Post %s: score=%s, min_comments=%s, filtered=True",
                        post_id,
                        post.get("score"),
                        filters.min_comments,
                        extra={
                            "operation": "reddit_filter",
                            "segment_name": segment_name,
                            "subreddit": subreddit,
                            "post_id": post_id,
                        },
                    )
                    continue

                logger.debug(
                    "Post %s: score=%s, min_score=%s, filtered=False",
                    post_id,
                    post.get("score"),
                    filters.min_score,
                    extra={
                        "operation": "reddit_filter",
                        "segment_name": segment_name,
                        "subreddit": subreddit,
                        "post_id": post_id,
                    },
                )
                curated.append(
                    {
                        "id": post_id,
                        "title": post.get("title", ""),
                        "url": post.get("url"),
                        "permalink": post.get("permalink"),
                        "created_utc": post.get("created_utc"),
                        "score": post.get("score", 0),
                        "num_comments": post.get("num_comments", 0),
                        "subreddit": subreddit,
                        "content_snippet": post.get("selftext", ""),
                    }
                )

        curated.sort(key=lambda item: item.get("score", 0), reverse=True)
        return curated, warnings

    def enrich_post(
        self,
        post: Dict[str, Any],
        *,
        segment_name: str,
        segment_config: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], List[str]]:
        headers = {"x-api-key": self.api_key}
        warnings: List[str] = []
        logger.debug(
            "Enriching Reddit post",
            extra={
                "operation": "reddit_enrich",
                "segment_name": segment_name,
                "post_id": post.get("id"),
            },
        )

        comments_payload: Any = {}
        if post.get("url"):
            try:
                start_time = time.perf_counter()
                response = requests.get(
                    SCRAPECREATORS_COMMENTS_URL,
                    headers=headers,
                    params={"url": post["url"]},
                    timeout=30,
                )
                response.raise_for_status()
                comments_payload = response.json() if response.content else {}
                logger.debug(
                    "Comments fetched",
                    extra={
                        "operation": "reddit_enrich",
                        "segment_name": segment_name,
                        "post_id": post.get("id"),
                        "duration_ms": round((time.perf_counter() - start_time) * 1000, 2),
                    },
                )
            except requests.RequestException as exc:
                warning = f"Failed to fetch comments for post '{post.get('id')}': {exc}"
                logger.warning(
                    warning,
                    extra={
                        "operation": "reddit_enrich",
                        "segment_name": segment_name,
                        "post_id": post.get("id"),
                    },
                )
                warnings.append(warning)

        discussion_text = self._build_discussion_summary(post, comments_payload)

        try:
            prompt_context = {
                "segment_name": segment_name,
                "audience": segment_config.get("audience", ""),
                "subreddit": post.get("subreddit", ""),
                "discussion_text": discussion_text,
            }
            response = self.gemini.generate_json_response(
                "voc_reddit_analysis_prompt.txt",
                prompt_context,
                model=self.advanced_model,
                temperature=0.2,
                max_output_tokens=1024,
            )
            if isinstance(response.data, dict):
                post["ai_analysis"] = response.data
            else:
                warnings.append("Gemini returned unexpected Reddit analysis structure.")
        except (GeminiClientError, FileNotFoundError) as exc:
            warning = f"Gemini Reddit analysis failed for post '{post.get('id')}': {exc}"
            logger.error(
                warning,
                extra={
                    "operation": "reddit_enrich",
                    "segment_name": segment_name,
                    "post_id": post.get("id"),
                },
            )
            warnings.append(warning)

        return post, warnings

    def _build_discussion_summary(self, post: Dict[str, Any], payload: Any) -> str:
        lines = [f"Title: {post.get('title', '')}"]
        body = post.get("content_snippet") or ""
        if body:
            lines.append("\nPost Body:\n" + body.strip())

        comments = self._extract_comment_bodies(payload)
        if comments:
            lines.append("\nTop Comments:\n" + "\n---\n".join(comments))
        return "\n\n".join(lines)

    @staticmethod
    def _extract_comment_bodies(payload: Any, limit: int = 5) -> List[str]:
        bodies: List[str] = []

        def _visit(node: Any) -> None:
            if len(bodies) >= limit:
                return
            if isinstance(node, dict):
                body = node.get("body")
                if isinstance(body, str):
                    trimmed = body.strip()
                    if trimmed and trimmed.lower() not in {"[deleted]", "[removed]"}:
                        bodies.append(trimmed)
                        if len(bodies) >= limit:
                            return
                for key in ("replies", "data", "children"):
                    value = node.get(key)
                    if isinstance(value, (dict, list)):
                        _visit(value)
            elif isinstance(node, list):
                for item in node:
                    if len(bodies) >= limit:
                        break
                    _visit(item)

        _visit(payload)
        return bodies[:limit]


def load_segment_config(segment_name: str) -> Dict[str, Any]:
    slug = segment_name.strip().lower().replace(" ", "_")
    config_path = (
        Path(__file__).resolve().parent
        / "config"
        / "prompts"
        / f"segment_{slug}.json"
    )
    if not config_path.exists():
        raise FileNotFoundError(f"No configuration found for segment '{segment_name}'.")
    logger.debug(
        "Segment config loaded",
        extra={
            "operation": "segment_config_load",
            "segment_name": segment_name,
            "config_path": str(config_path),
        },
    )
    return json.loads(config_path.read_text(encoding="utf-8"))


__all__ = [
    "RedditDataCollector",
    "RedditFilters",
    "RedditHistoryStore",
    "load_segment_config",
]

