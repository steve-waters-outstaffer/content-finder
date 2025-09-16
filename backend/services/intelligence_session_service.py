import uuid
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class IntelligenceSessionService:
    """Simple in-memory session service - no Firestore dependency"""
    
    def __init__(self):
        self.sessions = {}  # In-memory storage
    
    def create_session(self, segment_name, mission):
        """Create new intelligence session and return session ID"""
        session_id = str(uuid.uuid4())
        session_data = {
            'sessionId': session_id,
            'segmentName': segment_name,
            'mission': mission,
            'status': 'generating',
            'createdAt': datetime.now().isoformat(),
            'updatedAt': datetime.now().isoformat(),
            'queries': [],
            'searchResults': [],
            'themes': [],
            'stats': {
                'queries_generated': 0,
                'sources_found': 0,
                'sources_scraped': 0,
                'themes_generated': 0
            }
        }
        
        self.sessions[session_id] = session_data
        logger.info(f"Created intelligence session: {session_id}")
        return session_id
    
    def get_session(self, session_id):
        """Get session data by ID"""
        return self.sessions.get(session_id)
    
    def update_session_status(self, session_id, status):
        """Update session status"""
        if session_id in self.sessions:
            self.sessions[session_id]['status'] = status
            self.sessions[session_id]['updatedAt'] = datetime.now().isoformat()
            logger.info(f"Updated session {session_id} status to {status}")
    
    def save_queries(self, session_id, queries):
        """Save generated queries to session"""
        query_objects = [
            {
                'id': str(uuid.uuid4()),
                'text': query,
                'selected': True  # Default to selected
            }
            for query in queries
        ]
        
        if session_id in self.sessions:
            self.sessions[session_id]['queries'] = query_objects
            self.sessions[session_id]['status'] = 'queries_ready'
            self.sessions[session_id]['stats']['queries_generated'] = len(queries)
            self.sessions[session_id]['updatedAt'] = datetime.now().isoformat()
            logger.info(f"Saved {len(queries)} queries to session {session_id}")
    
    def update_query_selection(self, session_id, query_updates):
        """Update which queries are selected"""
        session = self.get_session(session_id)
        if not session:
            raise ValueError("Session not found")
        
        queries = session.get('queries', [])
        for update in query_updates:
            for query in queries:
                if query['id'] == update['id']:
                    query['selected'] = update['selected']
                    if 'text' in update:  # Allow query editing
                        query['text'] = update['text']
        
        self.sessions[session_id]['queries'] = queries
        self.sessions[session_id]['updatedAt'] = datetime.now().isoformat()
        logger.info(f"Updated query selections for session {session_id}")
    
    def save_search_results(self, session_id, search_results):
        """Save search results to session"""
        total_sources = sum(len(result.get('sources', [])) for result in search_results)
        
        if session_id in self.sessions:
            self.sessions[session_id]['searchResults'] = search_results
            self.sessions[session_id]['status'] = 'search_complete'
            self.sessions[session_id]['stats']['sources_found'] = total_sources
            self.sessions[session_id]['updatedAt'] = datetime.now().isoformat()
            logger.info(f"Saved search results with {total_sources} sources to session {session_id}")
    
    def update_source_selection(self, session_id, source_updates):
        """Update which sources are selected for analysis"""
        session = self.get_session(session_id)
        if not session:
            raise ValueError("Session not found")
        
        search_results = session.get('searchResults', [])
        for search_result in search_results:
            for source in search_result.get('sources', []):
                for update in source_updates:
                    if source['id'] == update['id']:
                        source['selected'] = update['selected']
        
        self.sessions[session_id]['searchResults'] = search_results
        self.sessions[session_id]['updatedAt'] = datetime.now().isoformat()
        logger.info(f"Updated source selections for session {session_id}")
    
    def save_analysis_results(self, session_id, themes, scraped_count):
        """Save analysis themes to session"""
        if session_id in self.sessions:
            self.sessions[session_id]['themes'] = themes
            self.sessions[session_id]['status'] = 'complete'
            self.sessions[session_id]['stats']['sources_scraped'] = scraped_count
            self.sessions[session_id]['stats']['themes_generated'] = len(themes)
            self.sessions[session_id]['updatedAt'] = datetime.now().isoformat()
            logger.info(f"Saved {len(themes)} themes to session {session_id}")
    
    def get_sessions_by_segment(self, segment_name, limit=10):
        """Get recent sessions for a segment"""
        segment_sessions = [
            session for session in self.sessions.values() 
            if session.get('segmentName') == segment_name
        ]
        
        # Sort by creation time (most recent first)
        segment_sessions.sort(key=lambda x: x['createdAt'], reverse=True)
        return segment_sessions[:limit]
