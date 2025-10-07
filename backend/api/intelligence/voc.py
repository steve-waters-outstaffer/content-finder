"""Voice of Customer discovery endpoint."""
from __future__ import annotations

import logging
import time

from flask import Blueprint, jsonify, request

from intelligence.voc_discovery import VOCDiscoveryError, run_voc_discovery

logger = logging.getLogger(__name__)

voc_bp = Blueprint("intelligence_voc", __name__)


@voc_bp.route("/intelligence/voc-discovery", methods=["POST"])
def voc_discovery():
    """Run the Voice of Customer discovery workflow for a given segment."""
    payload = request.get_json(silent=True) or {}
    segment_name = payload.get("segment_name")

    if not segment_name:
        logger.warning(
            "segment_name missing from discovery request",
            extra={"operation": "voc_discovery_request"},
        )
        return jsonify({"error": "segment_name is required"}), 400

    try:
        config_overrides = {
            key: value
            for key, value in payload.items()
            if key in {"google_trends", "trends_keywords", "subreddits"} and value
        }
        logger.info(
            "Starting VOC discovery",
            extra={
                "operation": "voc_discovery_start",
                "segment_name": segment_name,
            },
        )
        start_time = time.perf_counter()
        discovery_payload = run_voc_discovery(
            segment_name=segment_name,
            segment_config=config_overrides if config_overrides else None,
        )
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.info(
            "VOC discovery completed",
            extra={
                "operation": "voc_discovery_complete",
                "segment_name": segment_name,
                "duration_ms": duration_ms,
                "reddit_post_count": len(discovery_payload.get("reddit_posts", [])),
                "trends_count": len(discovery_payload.get("google_trends", [])),
            },
        )
        return jsonify(discovery_payload)
    except VOCDiscoveryError as exc:
        logger.warning(
            "VOC discovery failed with validation error",
            extra={
                "operation": "voc_discovery_error",
                "segment_name": segment_name,
                "error": str(exc),
            },
        )
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:  # noqa: BLE001 - bubble unexpected errors to caller
        logger.exception(
            "VOC discovery failed unexpectedly",
            extra={
                "operation": "voc_discovery_error",
                "segment_name": segment_name,
            },
        )
        return jsonify({"error": "Failed to run VOC discovery."}), 500
