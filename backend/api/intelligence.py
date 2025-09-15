"""Simple Intelligence API - No overcomplicated async stuff"""
import os
import json
import uuid
import requests
from datetime import datetime
from pathlib import Path
from flask import Blueprint, request, jsonify
import google.generativeai as genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Simple in-memory storage
sessions = {}

# Initialize APIs
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel('gemini-1.5-flash')

print(f"API Keys loaded - Gemini: {bool(GEMINI_API_KEY)}, Tavily: {bool(TAVILY_API_KEY)}")

def generate_queries_with_gemini(segment_name, mission):
    """Generate queries using Gemini AI"""
    if not GEMINI_API_KEY:
        # Fallback to basic queries if no API key
        return [
            f"latest trends in {segment_name.lower()} hiring",
            f"best practices for {segment_name.lower()} recruitment", 
            f"challenges in {segment_name.lower()} talent acquisition",
            f"technology solutions for {segment_name.lower()} teams",
            f"cost-effective strategies for {segment_name.lower()}"
        ]
    
    try:
        prompt = f"""
Generate 5 focused search queries for researching: {mission}

Target audience: {segment_name}

Requirements:
- Each query should be specific and searchable
- Focus on current trends, challenges, and solutions
- Suitable for web search engines
- Return ONLY the queries, one per line
- No numbering or formatting

Example format:
latest remote hiring trends for SMBs
cost-effective recruitment strategies 2024
SMB talent acquisition challenges
"""
        
        print(f"Generating queries for {segment_name}...")
        response = gemini_model.generate_content(prompt)
        
        if response.text:
            queries = [q.strip() for q in response.text.strip().split('\n') if q.strip()]
            print(f"Generated {len(queries)} queries")
            return queries[:5]  # Limit to 5
        
    except Exception as e:
        print(f"Gemini query generation failed: {e}")
    
    # Fallback to basic queries
    return [
        f"latest trends in {segment_name.lower()} hiring",
        f"best practices for {segment_name.lower()} recruitment", 
        f"challenges in {segment_name.lower()} talent acquisition",
        f"technology solutions for {segment_name.lower()} teams",
        f"cost-effective strategies for {segment_name.lower()}"
    ]

def search_with_tavily(query):
    """Search using Tavily API"""
    if not TAVILY_API_KEY:
        # Fallback to mock results if no API key
        return {
            'results': [
                {
                    'title': f'Mock Article about {query}',
                    'url': f'https://example.com/mock-article',
                    'content': f'This is mock content about {query}.'
                }
            ]
        }
    
    try:
        print(f"Searching: {query}")
        
        payload = {
            "api_key": TAVILY_API_KEY,
            "query": query,
            "max_results": 3,
            "search_depth": "advanced",
            "include_answer": True
        }
        
        response = requests.post("https://api.tavily.com/search", json=payload, timeout=30)
        
        if response.status_code == 200:
            result = response.json()
            print(f"Found {len(result.get('results', []))} results")
            return result
        else:
            print(f"Tavily search failed: {response.status_code}")
            
    except Exception as e:
        print(f"Tavily search error: {e}")
    
    # Fallback to mock result
    return {
        'results': [
            {
                'title': f'Search result for {query}',
                'url': f'https://example.com/search-result',
                'content': f'Content related to {query}.'
            }
        ]
    }

def analyze_content_with_gemini(sources, segment_name):
    """Analyze sources using Gemini AI to generate content themes"""
    if not GEMINI_API_KEY:
        # Fallback to mock themes if no API key
        return [
            {
                'theme': 'Technology Adoption',
                'key_insight': 'AI and automation tools are becoming essential for efficient recruiting',
                'why_smbs_care': 'Small teams can now handle larger candidate volumes with the right tools',
                'linkedin_angle': 'The democratization of recruiting technology'
            }
        ]
    
    try:
        # Prepare content for analysis
        content_snippets = []
        for source in sources:
            content_snippets.append(f"Title: {source.get('title', '')}\nURL: {source.get('url', '')}\nContent: {source.get('snippet', '')}")
        
        combined_content = "\n\n---\n\n".join(content_snippets[:10])  # Limit to prevent token overflow
        
        prompt = f"""
Analyze the following web search results about {segment_name} and generate 3 LinkedIn content themes.

Target Audience: {segment_name}

Content Sources:
{combined_content}

For each theme, provide:
1. Theme name (2-4 words)
2. Key insight (one clear sentence)
3. Why SMBs care (practical business reason)
4. LinkedIn angle (how to position this for social content)

Return your response in this exact JSON format:
[
  {{
    "theme": "Theme Name",
    "key_insight": "Main insight sentence",
    "why_smbs_care": "Why this matters to small businesses",
    "linkedin_angle": "How to frame this for LinkedIn content"
  }}
]

Requirements:
- Focus on actionable insights
- Make themes relevant to current business challenges
- Ensure LinkedIn angles are engaging and shareable
- Return ONLY valid JSON, no other text
"""

        print(f"Analyzing content for {segment_name}...")
        response = gemini_model.generate_content(prompt)
        
        if response.text:
            # Clean up response and parse JSON
            json_text = response.text.strip()
            # Remove any markdown code blocks if present
            if json_text.startswith('```json'):
                json_text = json_text.replace('```json', '').replace('```', '').strip()
            
            themes = json.loads(json_text)
            print(f"Generated {len(themes)} themes")
            return themes
        
    except Exception as e:
        print(f"Gemini content analysis failed: {e}")
    
    # Fallback to mock themes
    return [
        {
            'theme': 'Technology Trends',
            'key_insight': 'Modern recruiting technology is reshaping talent acquisition strategies',
            'why_smbs_care': 'Small businesses can now compete with enterprise-level recruiting capabilities',
            'linkedin_angle': 'How the right tools level the playing field for smaller companies'
        },
        {
            'theme': 'Process Innovation',
            'key_insight': 'Streamlined hiring processes are becoming competitive advantages',
            'why_smbs_care': 'Faster hiring means securing top talent before competitors',
            'linkedin_angle': 'Why your hiring speed might be your secret weapon'
        },
        {
            'theme': 'Market Insights',
            'key_insight': 'Industry shifts are creating new opportunities for strategic hiring',
            'why_smbs_care': 'Early adoption of new approaches can provide market advantages',
            'linkedin_angle': 'Spotting the trends that will define recruiting in 2024'
        }
    ]

intelligence_bp = Blueprint('intelligence', __name__)

@intelligence_bp.route('/intelligence/config', methods=['GET'])
def get_intelligence_config():
    """Get the intelligence configuration"""
    config = {
        'monthly_run': {
            'scrape_top': 5,
            'segments': [
                {
                    'name': 'SMB Leaders',
                    'description': 'Founders, COOs, and Hiring Managers at growing SMBs',
                    'research_focus': 'SMB hiring challenges, cost-effective strategies',
                    'content_goal': 'LinkedIn posts targeting SMB decision makers'
                },
                {
                    'name': 'Enterprise HR', 
                    'description': 'Talent Acquisition Managers and HR Directors',
                    'research_focus': 'Enterprise TA trends, technology adoption',
                    'content_goal': 'Strategic insights for HR leadership'
                },
                {
                    'name': 'Australian Developers',
                    'description': 'Software developers and tech companies in Australia',
                    'research_focus': 'Developer pain points, tool preferences',
                    'content_goal': 'Content for Australian developer community'
                }
            ]
        }
    }
    return jsonify(config)

@intelligence_bp.route('/intelligence/sessions', methods=['POST'])
def create_session():
    """Create session and generate queries"""
    try:
        data = request.get_json()
        segment_name = data.get('segment_name')
        mission = data.get('mission')

        # Create session
        session_id = str(uuid.uuid4())
        
        # Generate queries using Gemini AI
        base_queries = generate_queries_with_gemini(segment_name, mission)
        
        queries = [
            {
                'id': str(uuid.uuid4()),
                'text': query,
                'selected': True
            }
            for query in base_queries
        ]
        
        # Store session
        sessions[session_id] = {
            'sessionId': session_id,
            'segmentName': segment_name,
            'mission': mission,
            'status': 'queries_ready',
            'createdAt': datetime.now().isoformat(),
            'queries': queries,
            'searchResults': [],
            'themes': [],
            'stats': {
                'queries_generated': len(queries),
                'sources_found': 0,
                'themes_generated': 0
            }
        }
        
        return jsonify({
            'session_id': session_id,
            'session': sessions[session_id]
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
        data = request.get_json()
        query_updates = data.get('query_updates', [])
        
        session = sessions.get(session_id)
        if not session:
            return jsonify({'error': 'Session not found'}), 404
        
        # Update query selections
        for update in query_updates:
            for query in session['queries']:
                if query['id'] == update['id']:
                    query['selected'] = update['selected']
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@intelligence_bp.route('/intelligence/sessions/<session_id>/search', methods=['POST'])
def search_queries(session_id):
    """Process selected queries one by one"""
    try:
        session = sessions.get(session_id)
        if not session:
            return jsonify({'error': 'Session not found'}), 404
        
        session['status'] = 'searching'
        selected_queries = [q for q in session['queries'] if q['selected']]
        
        if not selected_queries:
            return jsonify({'error': 'No queries selected'}), 400
        
        search_results = []
        
        # Process each query with real Tavily search
        for i, query in enumerate(selected_queries):
            print(f"Processing query {i+1}/{len(selected_queries)}: {query['text']}")
            
            # Search with Tavily
            tavily_result = search_with_tavily(query['text'])
            
            # Convert Tavily results to our format
            sources = []
            for result in tavily_result.get('results', []):
                sources.append({
                    'id': str(uuid.uuid4()),
                    'title': result.get('title', 'No title'),
                    'url': result.get('url', ''),
                    'domain': result.get('url', '').split('/')[2] if result.get('url') else 'unknown',
                    'snippet': result.get('content', '')[:300],
                    'selected': True
                })
            
            search_results.append({
                'query': query['text'],
                'sources': sources
            })
        
        # Update session
        session['searchResults'] = search_results
        session['status'] = 'search_complete'
        session['stats']['sources_found'] = sum(len(r['sources']) for r in search_results)
        
        return jsonify({'success': True})
        
    except Exception as e:
        session['status'] = 'queries_ready'  # Reset on error
        return jsonify({'error': str(e)}), 500

@intelligence_bp.route('/intelligence/sessions/<session_id>/sources', methods=['PUT'])
def update_sources(session_id):
    """Update source selections"""
    try:
        data = request.get_json()
        source_updates = data.get('source_updates', [])
        
        session = sessions.get(session_id)
        if not session:
            return jsonify({'error': 'Session not found'}), 404
        
        # Update source selections
        for search_result in session['searchResults']:
            for source in search_result['sources']:
                for update in source_updates:
                    if source['id'] == update['id']:
                        source['selected'] = update['selected']
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@intelligence_bp.route('/intelligence/sessions/<session_id>/analyze', methods=['POST'])
def analyze_sources(session_id):
    """Analyze selected sources and generate themes"""
    try:
        session = sessions.get(session_id)
        if not session:
            return jsonify({'error': 'Session not found'}), 404
        
        session['status'] = 'analyzing'
        
        # Get selected sources
        selected_sources = []
        for search_result in session['searchResults']:
            for source in search_result['sources']:
                if source['selected']:
                    selected_sources.append(source)
        
        if not selected_sources:
            return jsonify({'error': 'No sources selected'}), 400
        
        print(f"Analyzing {len(selected_sources)} selected sources...")
        
        # Analyze content using Gemini AI
        themes = analyze_content_with_gemini(selected_sources, session['segmentName'])
        
        # Update session
        session['themes'] = themes
        session['status'] = 'complete'
        session['stats']['themes_generated'] = len(themes)
        
        return jsonify({
            'success': True,
            'sources_analyzed': len(selected_sources),
            'themes_generated': len(themes)
        })
        
    except Exception as e:
        session['status'] = 'search_complete'  # Reset on error
        return jsonify({'error': str(e)}), 500

# Optional: Progress endpoint for real-time updates
@intelligence_bp.route('/intelligence/sessions/<session_id>/progress', methods=['GET'])
def get_progress(session_id):
    """Get current processing progress"""
    session = sessions.get(session_id)
    if not session:
        return jsonify({'error': 'Session not found'}), 404
    
    return jsonify({
        'status': session['status'],
        'stats': session['stats']
    })
