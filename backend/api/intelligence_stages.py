"""
Staged VOC Discovery endpoints - breaks monolithic workflow into user-controlled steps.
Each endpoint completes one stage and returns results for user review before proceeding.
"""

import logging
import os
import time
from typing import Any, Dict

from flask import Blueprint, request, jsonify

from intelligence.voc_discovery import load_segment_config
from intelligence.voc_reddit import RedditDataCollector, RedditHistoryStore
from intelligence.voc_synthesis import filter_high_value_posts, generate_curated_queries
from intelligence.voc_trends import fetch_google_trends
from core.gemini_client import GeminiClient

logger = logging.getLogger(__name__)

stages_bp = Blueprint('voc_stages', __name__)


@stages_bp.route('/intelligence/voc-discovery/fetch-reddit', methods=['POST'])
def fetch_reddit():
    """
    Stage 1: Fetch raw Reddit posts from configured subreddits.
    Returns unfiltered posts for user review.
    """
    payload = request.get_json(silent=True) or {}
    segment_name = payload.get('segment_name')

    if not segment_name:
        return jsonify({'error': 'segment_name is required'}), 400

    try:
        logger.info(
            "Starting Reddit fetch",
            extra={
                "operation": "reddit_fetch_stage",
                "segment_name": segment_name,
            },
        )
        start_time = time.perf_counter()

        # Load config
        config = load_segment_config(segment_name)

        # Initialize collector
        gemini_client = GeminiClient()
        history_store = RedditHistoryStore.create()
        collector = RedditDataCollector(
            api_key=os.environ.get("SCRAPECREATORS_API_KEY"),
            gemini_client=gemini_client,
            history_store=history_store,
        )

        # Fetch posts (no enrichment yet)
        reddit_posts, warnings = collector.fetch_posts(
            segment_name=segment_name,
            segment_config=config,
        )

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.info(
            "Reddit fetch completed",
            extra={
                "operation": "reddit_fetch_stage",
                "segment_name": segment_name,
                "count": len(reddit_posts),
                "duration_ms": duration_ms,
            },
        )

        return jsonify({
            "raw_posts": reddit_posts,
            "count": len(reddit_posts),
            "warnings": warnings,
            "duration_ms": duration_ms,
        })

    except Exception as exc:
        logger.exception(
            "Reddit fetch failed",
            extra={
                "operation": "reddit_fetch_stage",
                "segment_name": segment_name,
            },
        )
        return jsonify({'error': str(exc)}), 500


@stages_bp.route('/intelligence/voc-discovery/analyze-posts', methods=['POST'])
def analyze_posts():
    """
    Stage 2: Filter posts with AI relevance scoring.
    Requires raw_posts from Stage 1.
    
    Note: The posts from fetch-reddit are already enriched with AI analysis.
    This stage just filters them based on relevance score.
    """
    payload = request.get_json(silent=True) or {}
    segment_name = payload.get('segment_name')
    raw_posts = payload.get('raw_posts', [])

    if not segment_name:
        return jsonify({'error': 'segment_name is required'}), 400

    if not raw_posts:
        logger.warning(
            "No raw_posts provided to analyze_posts",
            extra={
                "operation": "analyze_posts_stage",
                "segment_name": segment_name,
                "payload_keys": list(payload.keys()),
            },
        )
        return jsonify({
            'error': 'raw_posts is required (from fetch-reddit stage)',
            'received_keys': list(payload.keys()),
        }), 400

    try:
        logger.info(
            "Starting post filtering",
            extra={
                "operation": "analyze_posts_stage",
                "segment_name": segment_name,
                "post_count": len(raw_posts),
            },
        )
        start_time = time.perf_counter()

        # Load config
        config = load_segment_config(segment_name)

        # Filter high-value posts (posts are already enriched from stage 1)
        filtered_posts = filter_high_value_posts(
            raw_posts,
            config,
        )

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.info(
            "Post filtering completed",
            extra={
                "operation": "analyze_posts_stage",
                "segment_name": segment_name,
                "filtered_count": len(filtered_posts),
                "duration_ms": duration_ms,
            },
        )

        return jsonify({
            "filtered_posts": filtered_posts,
            "count": len(filtered_posts),
            "warnings": [],
            "duration_ms": duration_ms,
        })

    except Exception as exc:
        logger.exception(
            "Post filtering failed",
            extra={
                "operation": "analyze_posts_stage",
                "segment_name": segment_name,
            },
        )
        return jsonify({'error': str(exc)}), 500


@stages_bp.route('/intelligence/voc-discovery/fetch-trends', methods=['POST'])
def fetch_trends():
    """
    Stage 3: Fetch Google Trends data.
    Can run independently or in parallel with Stage 2.
    """
    payload = request.get_json(silent=True) or {}
    segment_name = payload.get('segment_name')

    if not segment_name:
        return jsonify({'error': 'segment_name is required'}), 400

    try:
        logger.info(
            "Starting trends fetch",
            extra={
                "operation": "trends_fetch_stage",
                "segment_name": segment_name,
            },
        )
        start_time = time.perf_counter()

        # Load config
        config = load_segment_config(segment_name)

        # Fetch trends
        trends_data, warnings = fetch_google_trends(config)

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.info(
            "Trends fetch completed",
            extra={
                "operation": "trends_fetch_stage",
                "segment_name": segment_name,
                "trends_count": len(trends_data),
                "duration_ms": duration_ms,
            },
        )

        return jsonify({
            "trends": trends_data,
            "count": len(trends_data),
            "warnings": warnings,
            "duration_ms": duration_ms,
        })

    except Exception as exc:
        logger.exception(
            "Trends fetch failed",
            extra={
                "operation": "trends_fetch_stage",
                "segment_name": segment_name,
            },
        )
        return jsonify({'error': str(exc)}), 500


@stages_bp.route('/intelligence/voc-discovery/generate-queries', methods=['POST'])
def generate_queries():
    """
    Stage 4: Generate curated research queries.
    Requires filtered_posts from Stage 2 and trends from Stage 3.
    """
    payload = request.get_json(silent=True) or {}
    segment_name = payload.get('segment_name')
    filtered_posts = payload.get('filtered_posts', [])
    trends = payload.get('trends', [])

    if not segment_name:
        return jsonify({'error': 'segment_name is required'}), 400

    try:
        logger.info(
            "Starting query generation",
            extra={
                "operation": "generate_queries_stage",
                "segment_name": segment_name,
                "posts_count": len(filtered_posts),
                "trends_count": len(trends),
            },
        )
        start_time = time.perf_counter()

        # Load config
        config = load_segment_config(segment_name)

        # Initialize Gemini client
        gemini_client = GeminiClient()

        # Generate queries
        curated_queries = generate_curated_queries(
            filtered_posts=filtered_posts,
            trends_data=trends,
            segment_config=config,
            gemini_client=gemini_client,
        )

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.info(
            "Query generation completed",
            extra={
                "operation": "generate_queries_stage",
                "segment_name": segment_name,
                "queries_count": len(curated_queries),
                "duration_ms": duration_ms,
            },
        )

        return jsonify({
            "queries": curated_queries,
            "count": len(curated_queries),
            "duration_ms": duration_ms,
        })

    except Exception as exc:
        logger.exception(
            "Query generation failed",
            extra={
                "operation": "generate_queries_stage",
                "segment_name": segment_name,
            },
        )
        return jsonify({'error': str(exc)}), 500
