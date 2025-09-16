# backend/api/synthesize.py
from flask import Blueprint, request, jsonify
from core.pipeline import ContentPipeline

synthesize_bp = Blueprint('synthesize', __name__)

@synthesize_bp.route('/synthesize', methods=['POST'])
def synthesize_content():
    """Synthesizes an article from multiple content sources"""
    data = request.get_json()
    query = data.get('query')
    contents = data.get('contents') # Expect a list of {url, title, markdown}

    if not contents or not isinstance(contents, list):
        return jsonify({'error': 'A list of content is required'}), 400
    if not query:
        return jsonify({'error': 'A query or topic is required'}), 400

    try:
        pipeline = ContentPipeline()
        # We'll create a new method in the pipeline for this
        result = pipeline.synthesize_article(query, contents)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500