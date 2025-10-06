# backend/api/synthesize.py

from flask import Blueprint, jsonify, request

from core.gemini_client import GeminiClientError
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

    pipeline = ContentPipeline()

    try:
        result = pipeline.synthesize_article(query, contents)
    except GeminiClientError as exc:
        return jsonify({'error': str(exc)}), 502
    except Exception as exc:  # noqa: BLE001 - surface unexpected issues
        return jsonify({'error': str(exc)}), 500

    return jsonify(result.model_dump())