"""Search API endpoint"""
from flask import Blueprint, request, jsonify
from core.pipeline import ContentPipeline


search_bp = Blueprint('search', __name__)


@search_bp.route('/search', methods=['POST'])
def search():
    """Search for content"""
    data = request.get_json()
    query = data.get('query')
    limit = data.get('limit', 15)
    
    if not query:
        return jsonify({'error': 'Query is required'}), 400
    
    try:
        pipeline = ContentPipeline()
        results = pipeline.search_only(query, limit)
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@search_bp.route('/pipeline', methods=['POST'])
def run_pipeline():
    """Run full content discovery pipeline"""
    data = request.get_json()
    query = data.get('query')
    max_urls = data.get('max_urls', 3)
    
    if not query:
        return jsonify({'error': 'Query is required'}), 400
    
    try:
        pipeline = ContentPipeline()
        results = pipeline.run_full_pipeline(query, max_urls)
        
        # Ensure all data is JSON serializable
        import json
        serializable_results = json.loads(json.dumps(results, default=str))
        
        return jsonify(serializable_results)
    except Exception as e:
        import traceback
        print(f"Pipeline error: {e}")
        print(traceback.format_exc())
        return jsonify({'error': str(e)}), 500
