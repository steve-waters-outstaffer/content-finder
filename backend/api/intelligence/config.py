"""Configuration-related endpoints for the intelligence API."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from flask import Blueprint, jsonify

from intelligence.voc_reddit import load_segment_config

logger = logging.getLogger(__name__)

config_bp = Blueprint("intelligence_config", __name__)


@config_bp.route("/intelligence/config", methods=["GET"])
def get_intelligence_config():
    """Return the intelligence configuration from the JSON file."""
    try:
        config_path = (
            Path(__file__).resolve().parent.parent.parent
            / "intelligence"
            / "config"
            / "intelligence_config.json"
        )
        logger.info(
            "Loading intelligence configuration",
            extra={
                "operation": "config_load",
                "config_path": str(config_path),
            },
        )
        with open(config_path, "r", encoding="utf-8") as file:
            config = json.load(file)
        logger.info(
            "Intelligence configuration loaded",
            extra={
                "operation": "config_load",
                "keys": list(config.keys()),
            },
        )
        return jsonify(config)
    except Exception as exc:  # noqa: BLE001 - expose failure to caller
        logger.error(
            "Failed to load intelligence configuration",
            exc_info=exc,
            extra={"operation": "config_load"},
        )
        return jsonify({"error": f"Failed to load configuration: {exc}"}), 500


@config_bp.route("/segment-config/<path:segment_name>", methods=["GET"])
def get_segment_config(segment_name: str):
    """Return the discovery configuration details for a specific segment."""
    try:
        logger.info(
            "Segment config requested",
            extra={
                "operation": "segment_config",
                "segment_name": segment_name,
            },
        )
        config = load_segment_config(segment_name)
    except FileNotFoundError as exc:
        logger.warning(
            "Segment configuration missing",
            extra={
                "operation": "segment_config",
                "segment_name": segment_name,
            },
        )
        return jsonify({"error": str(exc)}), 404
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Failed to load segment configuration",
            exc_info=exc,
            extra={
                "operation": "segment_config",
                "segment_name": segment_name,
            },
        )
        return (
            jsonify(
                {"error": f"Failed to load configuration for '{segment_name}': {exc}"}
            ),
            500,
        )

    subreddits = config.get("subreddits") or []
    trends_keywords = config.get("trends_keywords")

    if not trends_keywords:
        google_trends = config.get("google_trends") or {}
        trends_keywords = (
            google_trends.get("primary_keywords")
            or config.get("search_keywords")
            or []
        )

    return jsonify(
        {
            "segment": segment_name,
            "subreddits": subreddits,
            "trends_keywords": trends_keywords,
        }
    )
