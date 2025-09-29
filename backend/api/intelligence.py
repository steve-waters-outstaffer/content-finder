"""Simple Intelligence API using Agent-Based Research"""
import os
import json
import uuid
import asyncio
import requests
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
from intelligence.voc_discovery import VOCDiscoveryError, run_voc_discovery

# Load environment variables
load_dotenv()

DEFAULT_GEMINI_MODEL = os.getenv("MODEL", "gemini-2.5-flash")
_genai_client: Optional[genai.Client] = None


def _get_genai_client() -> Optional[genai.Client]:
    """Lazily instantiate and return a Gemini SDK client."""
    global _genai_client
    if _genai_client is not None:
        return _genai_client

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None

    _genai_client = genai.Client(api_key=api_key)
    return _genai_client

# Simple in-memory storage for sessions
sessions = {}

# Initialize the researcher once to be reused across requests for efficiency
try:
    researcher = AgentResearcher()
    print("AgentResearcher initialized successfully.")
except Exception as e:
    researcher = None
    print(f"CRITICAL: Failed to initialize AgentResearcher: {e}")

intelligence_bp = Blueprint('intelligence', __name__)

@intelligence_bp.route('/intelligence/config', methods=['GET'])
def get_intelligence_config():
    """Get the intelligence configuration from the JSON file"""
    try:
        # Construct a path to the config file relative to this file's location
        config_path = Path(__file__).parent.parent / 'intelligence' / 'config' / 'intelligence_config.json'
        with open(config_path, 'r') as f:
            config = json.load(f)
        return jsonify(config)
    except Exception as e:
        return jsonify({'error': f"Failed to load configuration: {str(e)}"}), 500


@intelligence_bp.route('/intelligence/voc-discovery', methods=['POST'])
def voc_discovery():
    """Run the Voice of Customer discovery workflow for a given segment."""

    payload = request.get_json(silent=True) or {}
    segment_name = payload.get('segment_name')

    if not segment_name:
        return jsonify({'error': 'segment_name is required'}), 400

    try:
        config_overrides = {
            key: value
            for key, value in payload.items()
            if key
            in {
                "enable_reddit",
                "enable_trends",
                "enable_curated_queries",
                "google_trends",
                "trends_keywords",
                "subreddits",
            }
        }
        discovery_payload = run_voc_discovery(
            segment_name=segment_name,
            segment_config=config_overrides or None,
        )
        return jsonify(discovery_payload)
    except VOCDiscoveryError as exc:
        return jsonify({'error': str(exc)}), 400
    except Exception as exc:  # noqa: BLE001 - ensure unexpected errors bubble to the client
        print(f"VOC discovery failed: {exc}")
        return jsonify({'error': 'Failed to run VOC discovery.'}), 500


@intelligence_bp.route('/intelligence/sessions', methods=['POST'])
def create_session():
    """Create a session and generate queries using the AgentResearcher"""
    if not researcher:
        return jsonify({'error': 'Intelligence agent is not available due to a configuration error.'}), 503

    try:
        data = request.get_json()
        segment_name = data.get('segment_name')
        mission = data.get('mission')  # This is the research_focus from the UI

        if not segment_name or not mission:
            return jsonify({'error': 'segment_name and mission are required'}), 400

        # Create a unique session ID
        session_id = str(uuid.uuid4())

        # Use the agent to generate queries asynchronously
        # In a standard Flask app, we run the async function using asyncio.run()
        print(f"Agent is planning queries for mission: {mission}")
        base_queries = asyncio.run(researcher.plan_queries(mission=mission, segment_name=segment_name))

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

        return jsonify({
            'session_id': session_id,
            'session': sessions[session_id]
        })

    except Exception as e:
        print(f"Error creating session: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

def search_with_tavily(query):
    """Search using Tavily API (kept for the search_queries route)"""
    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
    if not TAVILY_API_KEY:
        return {'results': [{'title': f'Mock result for {query}', 'url': 'https://example.com', 'content': 'This is mock content.'}]}

    try:
        print(f"Searching: {query}")
        payload = {"api_key": TAVILY_API_KEY, "query": query, "max_results": 5, "search_depth": "advanced"}
        response = requests.post("https://api.tavily.com/search", json=payload, timeout=30)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Tavily search failed: {response.status_code}")
            return {"results": []}
    except Exception as e:
        print(f"Tavily search error: {e}")
        return {"results": []}

def analyze_content_with_gemini(sources, segment):
    """Analyze sources using Gemini AI using an external prompt template."""
    client = _get_genai_client()
    if not client:
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

        response = client.models.generate_content(
            model=DEFAULT_GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.4,
                max_output_tokens=2048,
            ),
        )

        if response and response.text:
            json_text = response.text.strip().replace('```json', '').replace('```', '').strip()
            return json.loads(json_text)

    except Exception as e:
        print(f"Gemini content analysis failed: {e}")

    return [{'theme': 'Analysis Failed', 'key_insight': 'Could not analyze content.'}]


@intelligence_bp.route('/intelligence/sessions/<session_id>', methods=['GET'])
def get_session(session_id):
    """Get session data"""
    session = sessions.get(session_id)
    if not session:
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
            return jsonify({'error': 'Invalid payload: "queries" must be a list'}), 400

        session = sessions.get(session_id)
        if not session:
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
        return jsonify({'success': True})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@intelligence_bp.route('/intelligence/sessions/<session_id>/search', methods=['POST'])
def search_queries(session_id):
    """Process selected queries using Tavily"""
    try:
        session = sessions.get(session_id)
        if not session:
            return jsonify({'error': 'Session not found'}), 404

        session['status'] = 'searching'
        selected_queries = [q['text'] for q in session['queries'] if q['selected']]

        if not selected_queries:
            return jsonify({'error': 'No queries selected'}), 400

        search_results = []
        for query in selected_queries:
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

        return jsonify({'success': True})

    except Exception as e:
        if session:
            session['status'] = 'queries_ready'
        return jsonify({'error': str(e)}), 500

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
            return jsonify({'error': 'Invalid payload: "sources" must be a list'}), 400

        session = sessions.get(session_id)
        if not session:
            return jsonify({'error': 'Session not found'}), 404

        for search_result in session['searchResults']:
            for source in search_result['sources']:
                for update in source_updates:
                    update_id = update.get('id')
                    if update_id and source['id'] == update_id:
                        if 'selected' in update:
                            source['selected'] = bool(update['selected'])

        session['updatedAt'] = datetime.now().isoformat()
        return jsonify({'success': True})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# In backend/api/intelligence.py

@intelligence_bp.route('/intelligence/sessions/<session_id>/analyze', methods=['POST'])
def analyze_sources(session_id):
    """
    Scrapes selected sources and uses the AgentResearcher to analyze them and generate themes.
    """
    session = sessions.get(session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404

    if not researcher:
        return jsonify({'error': 'Intelligence agent is not available due to a configuration error.'}), 503

    try:
        session['status'] = 'analyzing'

        selected_sources = []
        for result in session.get('searchResults', []):
            for source in result.get('sources', []):
                if source.get('selected'):
                    selected_sources.append(source)

        if not selected_sources:
            return jsonify({'error': 'No sources selected for analysis'}), 400

        print(f"Scraping {len(selected_sources)} sources for analysis...")

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
        print(f"Successfully scraped {scraped_count}/{len(selected_sources)} sources.")

        if not successful_scrapes:
            raise Exception("Failed to scrape content from any of the selected sources.")

        print("Synthesizing insights from scraped content...")
        synthesis_result = asyncio.run(researcher.synthesize_insights(
            mission=session['mission'],
            segment_name=session['segmentName'],
            docs=successful_scrapes
        ))

        themes = synthesis_result.get("content_themes", [])
        session['themes'] = themes
        session['status'] = 'complete'
        session['stats']['sources_scraped'] = scraped_count
        session['stats']['themes_generated'] = len(themes)
        session['updatedAt'] = datetime.now().isoformat()

        print(f"Analysis complete for session {session_id}. Generated {len(themes)} themes.")

        return jsonify({'success': True, 'themes': themes})

    except Exception as e:
        if session:
            session['status'] = 'search_complete'
        print(f"Error during analysis: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500