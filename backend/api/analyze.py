"""Analysis API endpoint"""
from flask import Blueprint, request, jsonify
from core.pipeline import ContentPipeline


analyze_bp = Blueprint('analyze', __name__)


@analyze_bp.route('/analyze', methods=['POST'])
def analyze_content():
    """Analyze content with Gemini AI"""
    data = request.get_json() or {}
    content = data.get('content')
    custom_prompt = data.get('prompt')

    if not content:
        return jsonify({'error': 'Content is required'}), 400
    
    try:
        pipeline = ContentPipeline()
        result = pipeline.analyze_content(content, custom_prompt)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
