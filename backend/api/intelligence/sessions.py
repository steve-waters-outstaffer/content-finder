"""Session management endpoints for the intelligence API."""
from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from datetime import datetime
from typing import Any

import requests
from flask import Blueprint, jsonify, request

from .shared import researcher, sessions

logger = logging.getLogger(__name__)

sessions_bp = Blueprint("intelligence_sessions", __name__)


@sessions_bp.route("/intelligence/sessions", methods=["POST"])
def create_session():
    """Create a session and generate queries using the AgentResearcher."""
    if not researcher:
        logger.critical(
            "AgentResearcher unavailable during session creation",
            extra={"operation": "session_create"},
        )
        return jsonify(
            {"error": "Intelligence agent is not available due to a configuration error."}
        ), 503

    data = request.get_json(silent=True) or {}
    segment_name = data.get("segment_name")
    mission = data.get("mission")

    if not segment_name or not mission:
        logger.warning(
            "Invalid session creation payload",
            extra={
                "operation": "session_create",
                "segment_name": segment_name,
            },
        )
        return jsonify({"error": "segment_name and mission are required"}), 400

    try:
        session_id = str(uuid.uuid4())
        logger.info(
            "Planning queries for new session",
            extra={
                "operation": "session_create",
                "segment_name": segment_name,
                "session_id": session_id,
            },
        )
        start_time = time.perf_counter()
        base_queries = asyncio.run(
            researcher.plan_queries(mission=mission, segment_name=segment_name)
        )
        planning_duration = round((time.perf_counter() - start_time) * 1000, 2)

        if not base_queries:
            raise RuntimeError("Query generation failed to return any queries.")

        queries = [
            {"id": str(uuid.uuid4()), "text": query, "selected": True}
            for query in base_queries
        ]
        now_iso = datetime.now().isoformat()
        sessions[session_id] = {
            "sessionId": session_id,
            "segmentName": segment_name,
            "mission": mission,
            "status": "queries_ready",
            "createdAt": now_iso,
            "updatedAt": now_iso,
            "queries": queries,
            "searchResults": [],
            "themes": [],
            "stats": {
                "queries_generated": len(queries),
                "sources_found": 0,
                "sources_scraped": 0,
                "themes_generated": 0,
            },
        }

        logger.info(
            "Session created",
            extra={
                "operation": "session_create",
                "segment_name": segment_name,
                "session_id": session_id,
                "duration_ms": planning_duration,
                "count": len(queries),
            },
        )

        return jsonify({"session_id": session_id, "session": sessions[session_id]})
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Failed to create session",
            extra={
                "operation": "session_create",
                "segment_name": segment_name,
            },
        )
        return jsonify({"error": str(exc)}), 500


def _search_with_tavily(query: str) -> dict[str, Any]:
    """Search using the Tavily API (kept for the search_queries route)."""
    tavily_api_key = os.getenv("TAVILY_API_KEY")
    if not tavily_api_key:
        return {
            "results": [
                {
                    "title": f"Mock result for {query}",
                    "url": "https://example.com",
                    "content": "This is mock content.",
                }
            ]
        }

    try:
        logger.info(
            "Submitting Tavily search",
            extra={
                "operation": "tavily_search",
                "query": query,
            },
        )
        payload = {
            "api_key": tavily_api_key,
            "query": query,
            "max_results": 5,
            "search_depth": "advanced",
        }
        start_time = time.perf_counter()
        response = requests.post(
            "https://api.tavily.com/search", json=payload, timeout=30
        )
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        if response.status_code == 200:
            logger.info(
                "Tavily search succeeded",
                extra={
                    "operation": "tavily_search",
                    "query": query,
                    "duration_ms": duration_ms,
                },
            )
            return response.json()
        logger.error(
            "Tavily search failed",
            extra={
                "operation": "tavily_search",
                "query": query,
                "status_code": response.status_code,
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Tavily search raised exception",
            extra={
                "operation": "tavily_search",
                "query": query,
            },
        )
    return {"results": []}


@sessions_bp.route("/intelligence/sessions/<session_id>", methods=["GET"])
def get_session(session_id: str):
    """Return session data."""
    logger.debug(
        "Session fetch requested",
        extra={
            "operation": "session_get",
            "session_id": session_id,
        },
    )
    session = sessions.get(session_id)
    if not session:
        logger.warning(
            "Session not found",
            extra={
                "operation": "session_get",
                "session_id": session_id,
            },
        )
        return jsonify({"error": "Session not found"}), 404
    return jsonify(session)


@sessions_bp.route("/intelligence/sessions/<session_id>/queries", methods=["PUT"])
def update_queries(session_id: str):
    """Update query selections for a session."""
    try:
        data = request.get_json(silent=True) or {}
        query_updates = data.get("queries")
        if query_updates is None:
            query_updates = data.get("query", [])

        if not isinstance(query_updates, list):
            logger.warning(
                "Invalid query update payload",
                extra={
                    "operation": "session_queries_update",
                    "session_id": session_id,
                },
            )
            return jsonify({"error": 'Invalid payload: "queries" must be a list'}), 400

        session = sessions.get(session_id)
        if not session:
            logger.warning(
                "Session not found during query update",
                extra={
                    "operation": "session_queries_update",
                    "session_id": session_id,
                },
            )
            return jsonify({"error": "Session not found"}), 404

        for update in query_updates:
            update_id = update.get("id")
            if not update_id:
                continue
            for query in session["queries"]:
                if query["id"] == update_id:
                    if "selected" in update:
                        query["selected"] = bool(update["selected"])
                    if "text" in update and isinstance(update["text"], str):
                        query["text"] = update["text"]

        session["updatedAt"] = datetime.now().isoformat()
        logger.info(
            "Session queries updated",
            extra={
                "operation": "session_queries_update",
                "session_id": session_id,
                "count": len(query_updates),
            },
        )
        return jsonify({"success": True})
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Failed to update queries",
            extra={
                "operation": "session_queries_update",
                "session_id": session_id,
            },
        )
        return jsonify({"error": str(exc)}), 500


@sessions_bp.route("/intelligence/sessions/<session_id>/search", methods=["POST"])
def search_queries(session_id: str):
    """Process selected queries using Tavily."""
    session = sessions.get(session_id)
    if not session:
        logger.warning(
            "Session not found during search",
            extra={
                "operation": "session_search",
                "session_id": session_id,
            },
        )
        return jsonify({"error": "Session not found"}), 404

    session["status"] = "searching"
    selected_queries = [q["text"] for q in session["queries"] if q["selected"]]

    if not selected_queries:
        logger.warning(
            "No queries selected for search",
            extra={
                "operation": "session_search",
                "session_id": session_id,
            },
        )
        session["status"] = "queries_ready"
        return jsonify({"error": "No queries selected"}), 400

    try:
        search_results = []
        for query in selected_queries:
            logger.info(
                "Executing Tavily search for session",
                extra={
                    "operation": "session_search",
                    "session_id": session_id,
                    "query": query,
                },
            )
            tavily_result = _search_with_tavily(query)
            sources = [
                {
                    "id": str(uuid.uuid4()),
                    "title": result.get("title", "No title"),
                    "url": result.get("url", ""),
                    "domain": result.get("url", "").split("/")[2]
                    if result.get("url")
                    else "unknown",
                    "snippet": result.get("content", "")[:300],
                    "selected": True,
                }
                for result in tavily_result.get("results", [])
            ]
            search_results.append({"query": query, "sources": sources})

        session["searchResults"] = search_results
        session["status"] = "search_complete"
        session["stats"]["sources_found"] = sum(
            len(result["sources"]) for result in search_results
        )
        session["updatedAt"] = datetime.now().isoformat()

        logger.info(
            "Session search completed",
            extra={
                "operation": "session_search",
                "session_id": session_id,
                "count": session["stats"]["sources_found"],
            },
        )
        return jsonify({"success": True})
    except Exception as exc:  # noqa: BLE001
        session["status"] = "queries_ready"
        logger.exception(
            "Session search failed",
            extra={
                "operation": "session_search",
                "session_id": session_id,
            },
        )
        return jsonify({"error": str(exc)}), 500


@sessions_bp.route("/intelligence/sessions/<session_id>/sources", methods=["PUT"])
def update_sources(session_id: str):
    """Update source selections for a session."""
    try:
        data = request.get_json(silent=True) or {}
        source_updates = data.get("sources")
        if source_updates is None:
            source_updates = data.get("source_updates", [])

        if not isinstance(source_updates, list):
            logger.warning(
                "Invalid source update payload",
                extra={
                    "operation": "session_sources_update",
                    "session_id": session_id,
                },
            )
            return jsonify({"error": 'Invalid payload: "sources" must be a list'}), 400

        session = sessions.get(session_id)
        if not session:
            logger.warning(
                "Session not found during source update",
                extra={
                    "operation": "session_sources_update",
                    "session_id": session_id,
                },
            )
            return jsonify({"error": "Session not found"}), 404

        for search_result in session.get("searchResults", []):
            for source in search_result.get("sources", []):
                for update in source_updates:
                    update_id = update.get("id")
                    if update_id and source["id"] == update_id:
                        if "selected" in update:
                            source["selected"] = bool(update["selected"])

        session["updatedAt"] = datetime.now().isoformat()
        logger.info(
            "Session sources updated",
            extra={
                "operation": "session_sources_update",
                "session_id": session_id,
                "count": len(source_updates) if isinstance(source_updates, list) else 0,
            },
        )
        return jsonify({"success": True})
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Failed to update sources",
            extra={
                "operation": "session_sources_update",
                "session_id": session_id,
            },
        )
        return jsonify({"error": str(exc)}), 500


@sessions_bp.route("/intelligence/sessions/<session_id>/analyze", methods=["POST"])
def analyze_sources(session_id: str):
    """Scrape and analyze selected sources for a session."""
    session = sessions.get(session_id)
    if not session:
        logger.warning(
            "Session not found during analysis",
            extra={
                "operation": "session_analyze",
                "session_id": session_id,
            },
        )
        return jsonify({"error": "Session not found"}), 404

    if not researcher:
        logger.critical(
            "AgentResearcher unavailable during analysis",
            extra={
                "operation": "session_analyze",
                "session_id": session_id,
            },
        )
        return jsonify(
            {"error": "Intelligence agent is not available due to a configuration error."}
        ), 503

    try:
        session["status"] = "analyzing"

        selected_sources = [
            source
            for result in session.get("searchResults", [])
            for source in result.get("sources", [])
            if source.get("selected")
        ]

        if not selected_sources:
            logger.warning(
                "No sources selected for analysis",
                extra={
                    "operation": "session_analyze",
                    "session_id": session_id,
                },
            )
            session["status"] = "search_complete"
            return jsonify({"error": "No sources selected for analysis"}), 400

        logger.info(
            "ANALYSIS: Scraping %s sources for analysis",
            len(selected_sources),
            extra={
                "operation": "session_analyze",
                "session_id": session_id,
                "count": len(selected_sources),
            },
        )

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        scrape_tasks = [researcher.scrape_url(doc) for doc in selected_sources]
        scraped_docs = loop.run_until_complete(asyncio.gather(*scrape_tasks))
        loop.close()

        successful_scrapes = [doc for doc in scraped_docs if doc.get("passages")]
        scraped_count = len(successful_scrapes)
        logger.info(
            "ANALYSIS: Scraping completed. %s/%s successful.",
            scraped_count,
            len(selected_sources),
            extra={
                "operation": "session_analyze",
                "session_id": session_id,
                "count": scraped_count,
                "total_sources": len(selected_sources),
            },
        )

        if not successful_scrapes:
            raise RuntimeError("Failed to scrape content from any of the selected sources.")

        logger.info(
            "ANALYSIS: Synthesizing insights from %s documents.",
            scraped_count,
            extra={
                "operation": "session_analyze",
                "session_id": session_id,
                "count": scraped_count,
            },
        )

        synthesis_result = researcher.synthesize_insights(
            mission=session["mission"],
            segment_name=session["segmentName"],
            docs=successful_scrapes,
        )

        themes = synthesis_result.get("content_themes", [])
        session["themes"] = themes
        session["status"] = "complete"
        session["stats"]["sources_scraped"] = scraped_count
        session["stats"]["themes_generated"] = len(themes)
        session["updatedAt"] = datetime.now().isoformat()

        logger.info(
            "ANALYSIS: Analysis completed. Generated %s themes.",
            len(themes),
            extra={
                "operation": "session_analyze",
                "session_id": session_id,
                "count": len(themes),
            },
        )

        return jsonify({"success": True, "themes": themes})
    except Exception as exc:  # noqa: BLE001
        session["status"] = "search_complete"
        logger.exception(
            "Analysis failed",
            extra={
                "operation": "session_analyze",
                "session_id": session_id,
            },
        )
        return jsonify({"error": str(exc)}), 500
