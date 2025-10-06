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
        reddit_posts, raw_posts, warnings = collector.fetch_posts(
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
                "raw_count": len(raw_posts),
                "duration_ms": duration_ms,
            },
        )

        return jsonify({
            "raw_posts": reddit_posts,  # Filtered posts (for backward compatibility)
            "unfiltered_posts": raw_posts,  # NEW: All posts before filtering
            "count": len(reddit_posts),
            "raw_count": len(raw_posts),
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


@stages_bp.route('/intelligence/voc-discovery/pre-score-posts', methods=['POST'])
def pre_score_posts():
    """
    Stage 2: Batch pre-score posts using AI (title + snippet only, no comments).
    Fast relevance scoring to filter down to promising posts.
    """
    payload = request.get_json(silent=True) or {}
    segment_name = payload.get('segment_name')
    raw_posts = payload.get('raw_posts', [])

    if not segment_name:
        return jsonify({'error': 'segment_name is required'}), 400

    if not raw_posts:
        return jsonify({'error': 'raw_posts is required (from fetch-reddit stage)'}), 400

    try:
        logger.info(
            "Starting batch pre-score",
            extra={
                "operation": "prescore_stage",
                "segment_name": segment_name,
                "post_count": len(raw_posts),
            },
        )
        start_time = time.perf_counter()

        # Load config
        config = load_segment_config(segment_name)
        gemini_client = GeminiClient()
        
        # Pre-score using title + snippet only (fast)
        from intelligence.voc_synthesis import pre_score_posts

        prescored_posts, warnings = pre_score_posts(
            raw_posts,
            segment_name,
            gemini_client=gemini_client,
            segment_config=config,
        )
        
        # Filter by prescore threshold
        min_prescore = config.get('prescore_threshold', 6.0)
        promising_posts = [
            p for p in prescored_posts 
            if p.get('prescore', {}).get('relevance_score', 0) >= min_prescore
        ]
        rejected_posts = [
            p for p in prescored_posts 
            if p.get('prescore', {}).get('relevance_score', 0) < min_prescore
        ]

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.info(
            "Batch pre-score completed",
            extra={
                "operation": "prescore_stage",
                "segment_name": segment_name,
                "prescored_count": len(prescored_posts),
                "promising_count": len(promising_posts),
                "threshold": min_prescore,
                "duration_ms": duration_ms,
            },
        )

        return jsonify({
            "prescored_posts": prescored_posts,
            "promising_posts": promising_posts,
            "rejected_posts": rejected_posts,
            "count": len(promising_posts),
            "stats": {
                "input": len(raw_posts),
                "prescored": len(prescored_posts),
                "promising": len(promising_posts),
                "rejected": len(rejected_posts),
            },
            "threshold": min_prescore,
            "warnings": warnings,
            "duration_ms": duration_ms,
        })

    except Exception as exc:
        logger.exception(
            "Pre-score failed",
            extra={
                "operation": "prescore_stage",
                "segment_name": segment_name,
            },
        )
        return jsonify({'error': str(exc)}), 500


@stages_bp.route('/intelligence/voc-discovery/enrich-posts', methods=['POST'])
def enrich_posts():
    """
    Stage 3: Deep enrichment with comments for high-scoring posts.
    Fetches comments and runs full AI analysis.
    """
    payload = request.get_json(silent=True) or {}
    segment_name = payload.get('segment_name')
    promising_posts = payload.get('promising_posts', [])

    if not segment_name:
        return jsonify({'error': 'segment_name is required'}), 400

    if not promising_posts:
        return jsonify({'error': 'promising_posts is required (from pre-score stage)'}), 400

    try:
        logger.info(
            "Starting deep enrichment",
            extra={
                "operation": "enrich_stage",
                "segment_name": segment_name,
                "post_count": len(promising_posts),
            },
        )
        start_time = time.perf_counter()

        # Load config
        config = load_segment_config(segment_name)
        gemini_client = GeminiClient()
        history_store = RedditHistoryStore.create()
        collector = RedditDataCollector(
            api_key=os.environ.get("SCRAPECREATORS_API_KEY"),
            gemini_client=gemini_client,
            history_store=history_store,
        )
        
        # Deep enrichment with comments
        enriched_posts = []
        warnings = []
        for post in promising_posts:
            enriched_post, post_warnings = collector.enrich_post(
                post,
                segment_name=segment_name,
                segment_config=config,
            )
            enriched_posts.append(enriched_post)
            warnings.extend(post_warnings)

        # Final filter based on deep AI analysis
        final_threshold = config.get('ai_relevance_threshold', 6.0)
        filtered_posts, rejected_posts = filter_high_value_posts(
            enriched_posts,
            min_score=final_threshold,
        )

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.info(
            "Deep enrichment completed",
            extra={
                "operation": "enrich_stage",
                "segment_name": segment_name,
                "enriched_count": len(enriched_posts),
                "filtered_count": len(filtered_posts),
                "threshold": final_threshold,
                "duration_ms": duration_ms,
            },
        )

        return jsonify({
            "filtered_posts": filtered_posts,
            "rejected_posts": rejected_posts,
            "count": len(filtered_posts),
            "stats": {
                "input": len(promising_posts),
                "enriched": len(enriched_posts),
                "final_accepted": len(filtered_posts),
                "final_rejected": len(rejected_posts),
            },
            "threshold": final_threshold,
            "warnings": warnings,
            "duration_ms": duration_ms,
        })

    except Exception as exc:
        logger.exception(
            "Enrichment failed",
            extra={
                "operation": "enrich_stage",
                "segment_name": segment_name,
            },
        )
        return jsonify({'error': str(exc)}), 500


@stages_bp.route('/intelligence/voc-discovery/analyze-posts', methods=['POST'])
def analyze_posts():
    """
    DEPRECATED: This endpoint combined pre-scoring and enrichment.
    Use /pre-score-posts and /enrich-posts instead.
    
    Kept for backwards compatibility - redirects to pre-score endpoint.
    """
    return jsonify({
        'error': 'This endpoint is deprecated. Use /pre-score-posts then /enrich-posts instead.',
        'suggestion': 'Call /pre-score-posts first, then /enrich-posts with the promising_posts'
    }), 410  # 410 Gone


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
