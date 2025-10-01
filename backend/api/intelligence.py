"""Simple Intelligence API using Agent-Based Research"""
import asyncio
import json
import logging
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from flask import Blueprint, request, jsonify
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Add backend directory to path to allow imports from sibling directories
import sys
sys.path.append(str(Path(__file__).resolve().parent.parent))

from intelligence.agent_research import AgentResearcher
from intelligence.voc_discovery import (
    VOCDiscoveryError,
    run_voc_discovery,
)
from intelligence.voc_reddit import load_segment_config

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

DEFAULT_GEMINI_MODEL = os.getenv("MODEL", "gemini-2.5-flash")
_genai_client: Optional[genai.Client] = None


def _get_genai_client() -> Optional[genai.Client]:
    """Lazily instantiate and return a Gemini SDK client."""
    global _genai_client
    logger.debug(
        "Gemini client requested",
        extra={"operation": "gemini_client_init"},
    )
    if _genai_client is not None:
        return _genai_client

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.warning(
            "GEMINI_API_KEY missing; Gemini client unavailable",
            extra={"operation": "gemini_client_init"},
        )
        return None

    _genai_client = genai.Client(api_key=api_key)
    logger.info(
        "Gemini client initialized",
        extra={"operation": "gemini_client_init"},
    )
    return _genai_client

# Simple in-memory storage for sessions
sessions = {}

# Initialize the researcher once to be reused across requests for efficiency
try:
    start_time = time.perf_counter()
    researcher = AgentResearcher()
    logger.info(
        "AgentResearcher initialized successfully",
        extra={
            "operation": "agent_init",
            "duration_ms": round((time.perf_counter() - start_time) * 1000, 2),
        },
    )
except Exception as exc:  # noqa: BLE001 - propagate through logging with stack trace
    researcher = None
    logger.critical(
        "Failed to initialize AgentResearcher",
        exc_info=exc,
        extra={"operation": "agent_init"},
    )

intelligence_bp = Blueprint('intelligence', __name__)

@intelligence_bp.route('/intelligence/config', methods=['GET'])
def get_intelligence_config():
    """Get the intelligence configuration from the JSON file"""
    try:
        # Construct a path to the config file relative to this file's location
        config_path = Path(__file__).parent.parent / 'intelligence' / 'config' / 'intelligence_config.json'
        logger.info(
            "Loading intelligence configuration",
            extra={
                "operation": "config_load",
                "config_path": str(config_path),
            },
        )
        with open(config_path, 'r') as f:
            config = json.load(f)
        logger.info(
            "Intelligence configuration loaded",
            extra={
                "operation": "config_load",
                "keys": list(config.keys()),
            },
        )
        return jsonify(config)
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Failed to load intelligence configuration",
            exc_info=exc,
            extra={"operation": "config_load"},
        )
        return jsonify({'error': f"Failed to load configuration: {str(exc)}"}), 500


@intelligence_bp.route('/segment-config/<path:segment_name>', methods=['GET'])
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
        return jsonify({'error': str(exc)}), 404
    except Exception as exc:  # noqa: BLE001 - surface unexpected failures to client
        logger.error(
            "Failed to load segment configuration",
            exc_info=exc,
            extra={
                "operation": "segment_config",
                "segment_name": segment_name,
            },
        )
        return (
            jsonify({'error': f"Failed to load configuration for '{segment_name}': {exc}"}),
            500,
        )

    subreddits = config.get('subreddits') or []
    trends_keywords = config.get('trends_keywords')

    if not trends_keywords:
        google_trends = config.get('google_trends') or {}
        trends_keywords = (
            google_trends.get('primary_keywords')
            or config.get('search_keywords')
            or []
        )

    return jsonify(
        {
            'segment': segment_name,
            'subreddits': subreddits,
            'trends_keywords': trends_keywords,
        }
    )


@intelligence_bp.route('/intelligence/voc-discovery', methods=['POST'])
def voc_discovery():
    """Run the Voice of Customer discovery workflow for a given segment."""

    payload = request.get_json(silent=True) or {}
    segment_name = payload.get('segment_name')

    if not segment_name:
        logger.warning(
            "segment_name missing from discovery request",
            extra={"operation": "voc_discovery_request"},
        )
        return jsonify({'error': 'segment_name is required'}), 400

    try:
        # Only accept actual data overrides, not enable flags
        # Enable flags without data shouldn't override file config
        config_overrides = {
            key: value
            for key, value in payload.items()
            if key in {"google_trends", "trends_keywords", "subreddits"}
            and value  # Only include if value is truthy (not empty list/dict)
        }
        logger.debug(f"Raw payload received: {payload}", extra={"operation": "voc_discovery_request", "segment_name": segment_name})
        logger.debug(
            f"Config overrides extracted: {config_overrides}",
            extra={
                "operation": "voc_discovery_request",
                "segment_name": segment_name,
            },
        )
        logger.info(
            f"Starting VOC discovery for segment: {segment_name}",
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
                "reddit_post_count": len(discovery_payload.get('reddit_posts', [])),
                "trends_count": len(discovery_payload.get('google_trends', [])),
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
        return jsonify({'error': str(exc)}), 400
    except Exception as exc:  # noqa: BLE001 - ensure unexpected errors bubble to the client
        logger.exception(
            "VOC discovery failed unexpectedly",
            extra={
                "operation": "voc_discovery_error",
                "segment_name": segment_name,
            },
        )
        return jsonify({'error': 'Failed to run VOC discovery.'}), 500


@intelligence_bp.route('/intelligence/sessions', methods=['POST'])
def create_session():
    """Create a session and generate queries using the AgentResearcher"""
    if not researcher:
        logger.critical(
            "AgentResearcher unavailable during session creation",
            extra={"operation": "session_create"},
        )
        return jsonify({'error': 'Intelligence agent is not available due to a configuration error.'}), 503

    try:
        data = request.get_json()
        segment_name = data.get('segment_name')
        mission = data.get('mission')  # This is the research_focus from the UI

        if not segment_name or not mission:
            logger.warning(
                "Invalid session creation payload",
                extra={
                    "operation": "session_create",
                    "segment_name": segment_name,
                },
            )
            return jsonify({'error': 'segment_name and mission are required'}), 400

        # Create a unique session ID
        session_id = str(uuid.uuid4())

        # Use the agent to generate queries asynchronously
        # In a standard Flask app, we run the async function using asyncio.run()
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
            raise Exception("Query generation failed to return any queries.")

        queries = [
            {'id': str(uuid.uuid4()), 'text': query, 'selected': True}
            for query in base_queries
        ]

        # Store the new session in our in-memory dictionary
        sessions[session_id] = {
            'sessionId': session_id,
            'segmentName': segment_name,
            'mission': mission,
            'status': 'queries_ready',
            'createdAt': datetime.now().isoformat(),
            'updatedAt': datetime.now().isoformat(),
            'queries': queries,
            'searchResults': [],
            'themes': [],
            'stats': {
                'queries_generated': len(queries),
                'sources_found': 0,
                'sources_scraped': 0,
                'themes_generated': 0
            }
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

        return jsonify({
            'session_id': session_id,
            'session': sessions[session_id]
        })

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Failed to create session",
            extra={
                "operation": "session_create",
                "segment_name": segment_name,
            },
        )
        return jsonify({'error': str(exc)}), 500

def search_with_tavily(query):
    """Search using Tavily API (kept for the search_queries route)"""
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
    if not TAVILY_API_KEY:
        return {'results': [{'title': f'Mock result for {query}', 'url': 'https://example.com', 'content': 'This is mock content.'}]}

    try:
        logger.info(
            "Submitting Tavily search",
            extra={
                "operation": "tavily_search",
                "query": query,
            },
        )
        payload = {"api_key": TAVILY_API_KEY, "query": query, "max_results": 5, "search_depth": "advanced"}
        start_time = time.perf_counter()
        response = requests.post("https://api.tavily.com/search", json=payload, timeout=30)
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
        else:
            logger.error(
                "Tavily search failed",
                extra={
                    "operation": "tavily_search",
                    "query": query,
                    "status_code": response.status_code,
                },
            )
            return {"results": []}
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Tavily search raised exception",
            extra={
                "operation": "tavily_search",
                "query": query,
            },
        )
        return {"results": []}

def analyze_content_with_gemini(sources, segment):
    """Analyze sources using Gemini AI using an external prompt template."""
    client = _get_genai_client()
    if not client:
        logger.warning(
            "Gemini client unavailable for content analysis",
            extra={
                "operation": "gemini_content_analysis",
            },
        )
        return [{'theme': 'Fallback Theme', 'key_insight': 'API key missing.'}]

    try:
        content_snippets = [
            f"Title: {source.get('title', '')}\nURL: {source.get('url', '')}\nContent: {source.get('snippet', '')}"
            for source in sources
        ]
        combined_content = "\n\n---\n\n".join(content_snippets[:10])

        prompt_path = Path(__file__).parent.parent / 'intelligence' / 'config' / 'prompts' / 'synthesis_prompt.txt'
        with open(prompt_path, 'r') as f:
            prompt_template = f.read()

        # MODIFICATION 2: Populate the template with both name and description
        prompt = prompt_template.format(
            segment_name=segment.get('name', 'Unknown Audience'),
            segment_description=segment.get('description', 'No description provided.'),
            combined_content=combined_content
        )

        start_time = time.perf_counter()
        response = client.models.generate_content(
            model=DEFAULT_GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.4,
                max_output_tokens=2048,
            ),
        )
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        if response and response.text:
            json_text = response.text.strip().replace('```json', '').replace('```', '').strip()
            insights = json.loads(json_text)
            logger.info(
                "Gemini content analysis succeeded",
                extra={
                    "operation": "gemini_content_analysis",
                    "segment_name": segment.get('name'),
                    "duration_ms": duration_ms,
                },
            )
            return insights

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Gemini content analysis failed",
            extra={
                "operation": "gemini_content_analysis",
                "segment_name": segment.get('name'),
            },
        )

    return [{'theme': 'Analysis Failed', 'key_insight': 'Could not analyze content.'}]


@intelligence_bp.route('/intelligence/sessions/<session_id>', methods=['GET'])
def get_session(session_id):
    """Get session data"""
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
        return jsonify({'error': 'Session not found'}), 404
    return jsonify(session)

@intelligence_bp.route('/intelligence/sessions/<session_id>/queries', methods=['PUT'])
def update_queries(session_id):
    """Update query selections"""
    try:
        data = request.get_json() or {}
        query_updates = data.get('queries')
        if query_updates is None:
            # Backwards compatibility with earlier payload shape
            query_updates = data.get('query', [])

        if not isinstance(query_updates, list):
            logger.warning(
                "Invalid query update payload",
                extra={
                    "operation": "session_queries_update",
                    "session_id": session_id,
                },
            )
            return jsonify({'error': 'Invalid payload: "queries" must be a list'}), 400

        session = sessions.get(session_id)
        if not session:
            logger.warning(
                "Session not found during query update",
                extra={
                    "operation": "session_queries_update",
                    "session_id": session_id,
                },
            )
            return jsonify({'error': 'Session not found'}), 404

        for update in query_updates:
            update_id = update.get('id')
            if not update_id:
                continue

            for query in session['queries']:
                if query['id'] == update_id:
                    if 'selected' in update:
                        query['selected'] = bool(update['selected'])
                    if 'text' in update and isinstance(update['text'], str):
                        query['text'] = update['text']

        session['updatedAt'] = datetime.now().isoformat()
        logger.info(
            "Session queries updated",
            extra={
                "operation": "session_queries_update",
                "session_id": session_id,
                "count": len(query_updates),
            },
        )
        return jsonify({'success': True})

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Failed to update queries",
            extra={
                "operation": "session_queries_update",
                "session_id": session_id,
            },
        )
        return jsonify({'error': str(exc)}), 500

@intelligence_bp.route('/intelligence/sessions/<session_id>/search', methods=['POST'])
def search_queries(session_id):
    """Process selected queries using Tavily"""
    try:
        session = sessions.get(session_id)
        if not session:
            logger.warning(
                "Session not found during search",
                extra={
                    "operation": "session_search",
                    "session_id": session_id,
                },
            )
            return jsonify({'error': 'Session not found'}), 404

        session['status'] = 'searching'
        selected_queries = [q['text'] for q in session['queries'] if q['selected']]

        if not selected_queries:
            logger.warning(
                "No queries selected for search",
                extra={
                    "operation": "session_search",
                    "session_id": session_id,
                },
            )
            return jsonify({'error': 'No queries selected'}), 400

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
            tavily_result = search_with_tavily(query)
            sources = [
                {
                    'id': str(uuid.uuid4()),
                    'title': result.get('title', 'No title'),
                    'url': result.get('url', ''),
                    'domain': result.get('url', '').split('/')[2] if result.get('url') else 'unknown',
                    'snippet': result.get('content', '')[:300],
                    'selected': True
                }
                for result in tavily_result.get('results', [])
            ]
            search_results.append({'query': query, 'sources': sources})

        session['searchResults'] = search_results
        session['status'] = 'search_complete'
        session['stats']['sources_found'] = sum(len(r['sources']) for r in search_results)
        session['updatedAt'] = datetime.now().isoformat()

        logger.info(
            "Session search completed",
            extra={
                "operation": "session_search",
                "session_id": session_id,
                "count": session['stats']['sources_found'],
            },
        )
        return jsonify({'success': True})

    except Exception as exc:  # noqa: BLE001
        if session:
            session['status'] = 'queries_ready'
        logger.exception(
            "Session search failed",
            extra={
                "operation": "session_search",
                "session_id": session_id,
            },
        )
        return jsonify({'error': str(exc)}), 500

@intelligence_bp.route('/intelligence/sessions/<session_id>/sources', methods=['PUT'])
def update_sources(session_id):
    """Update source selections"""
    try:
        data = request.get_json() or {}
        source_updates = data.get('sources')
        if source_updates is None:
            # Backwards compatibility with earlier payload shape
            source_updates = data.get('source_updates', [])

        if not isinstance(source_updates, list):
            logger.warning(
                "Invalid source update payload",
                extra={
                    "operation": "session_sources_update",
                    "session_id": session_id,
                },
            )
            return jsonify({'error': 'Invalid payload: "sources" must be a list'}), 400

        session = sessions.get(session_id)
        if not session:
            logger.warning(
                "Session not found during source update",
                extra={
                    "operation": "session_sources_update",
                    "session_id": session_id,
                },
            )
            return jsonify({'error': 'Session not found'}), 404

        for search_result in session['searchResults']:
            for source in search_result['sources']:
                for update in source_updates:
                    update_id = update.get('id')
                    if update_id and source['id'] == update_id:
                        if 'selected' in update:
                            source['selected'] = bool(update['selected'])

        session['updatedAt'] = datetime.now().isoformat()
        logger.info(
            "Session sources updated",
            extra={
                "operation": "session_sources_update",
                "session_id": session_id,
                "count": len(source_updates) if isinstance(source_updates, list) else 0,
            },
        )
        return jsonify({'success': True})

    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "Failed to update sources",
            extra={
                "operation": "session_sources_update",
                "session_id": session_id,
            },
        )
        return jsonify({'error': str(exc)}), 500

# In backend/api/intelligence.py

@intelligence_bp.route('/intelligence/sessions/<session_id>/analyze', methods=['POST'])
def analyze_sources(session_id):
    """
    Scrapes selected sources and uses the AgentResearcher to analyze them and generate themes.
    """
    session = sessions.get(session_id)
    if not session:
        logger.warning(
            "Session not found during analysis",
            extra={
                "operation": "session_analyze",
                "session_id": session_id,
            },
        )
        return jsonify({'error': 'Session not found'}), 404

    if not researcher:
        logger.critical(
            "AgentResearcher unavailable during analysis",
            extra={
                "operation": "session_analyze",
                "session_id": session_id,
            },
        )
        return jsonify({'error': 'Intelligence agent is not available due to a configuration error.'}), 503

    try:
        session['status'] = 'analyzing'

        selected_sources = []
        for result in session.get('searchResults', []):
            for source in result.get('sources', []):
                if source.get('selected'):
                    selected_sources.append(source)

        if not selected_sources:
            logger.warning(
                "No sources selected for analysis",
                extra={
                    "operation": "session_analyze",
                    "session_id": session_id,
                },
            )
            return jsonify({'error': 'No sources selected for analysis'}), 400

        logger.info(
            "Scraping sources for analysis",
            extra={
                "operation": "session_analyze",
                "session_id": session_id,
                "count": len(selected_sources),
            },
        )

        # --- THIS IS THE FIX ---
        # Manually manage the asyncio event loop for threads
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        scrape_tasks = [researcher.scrape_url(doc) for doc in selected_sources]
        scraped_docs = loop.run_until_complete(asyncio.gather(*scrape_tasks))
        loop.close()
        # --- END OF FIX ---

        successful_scrapes = [doc for doc in scraped_docs if doc.get('passages')]
        scraped_count = len(successful_scrapes)
        logger.info(
            "Scraping completed",
            extra={
                "operation": "session_analyze",
                "session_id": session_id,
                "count": scraped_count,
                "total_sources": len(selected_sources),
            },
        )

        if not successful_scrapes:
            raise Exception("Failed to scrape content from any of the selected sources.")

        logger.info(
            "Synthesizing insights",
            extra={
                "operation": "session_analyze",
                "session_id": session_id,
                "count": scraped_count,
            },
        )
        logger.info(f"Starting synthesis for session {session_id}")
        logger.debug(f"Number of docs to synthesize: {len(successful_scrapes)}")

        try:
            synthesis_result = researcher.synthesize_insights(
                mission=session['mission'],
                segment_name=session['segmentName'],
                docs=successful_scrapes
            )
            logger.info("Synthesis completed successfully")
            logger.debug(f"Synthesis result keys: {synthesis_result.keys()}")
        except Exception as e:  # noqa: BLE001
            logger.error(f"Synthesis failed: {str(e)}", exc_info=True)
            raise

        themes = synthesis_result.get("content_themes", [])
        session['themes'] = themes
        session['status'] = 'complete'
        session['stats']['sources_scraped'] = scraped_count
        session['stats']['themes_generated'] = len(themes)
        session['updatedAt'] = datetime.now().isoformat()

        logger.info(
            "Analysis completed",
            extra={
                "operation": "session_analyze",
                "session_id": session_id,
                "count": len(themes),
            },
        )

        return jsonify({'success': True, 'themes': themes})

    except Exception as exc:  # noqa: BLE001
        if session:
            session['status'] = 'search_complete'
        logger.exception(
            "Analysis failed",
            extra={
                "operation": "session_analyze",
                "session_id": session_id,
            },
        )
        return jsonify({'error': str(exc)}), 500