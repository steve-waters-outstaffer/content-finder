"""Analysis API endpoint"""

from flask import Blueprint, jsonify, request

from core.gemini_client import GeminiClientError
from core.pipeline import ContentPipeline


analyze_bp = Blueprint('analyze', __name__)


@analyze_bp.route('/analyze', methods=['POST'])
def analyze_content():
    """Analyze content with Gemini AI"""
    data = request.get_json()
    content = data.get('content')
    custom_prompt = data.get('prompt')
    
    if not content:
        return jsonify({'error': 'Content is required'}), 400
    
    pipeline = ContentPipeline()

    try:
        analysis = pipeline.analyze_content(content, custom_prompt)
    except ValueError as exc:  # custom prompt not supported
        return jsonify({'error': str(exc)}), 400
    except GeminiClientError as exc:
        return jsonify({'error': str(exc)}), 502
    except Exception as exc:  # noqa: BLE001 - surface unexpected issues
        return jsonify({'error': str(exc)}), 500

    return jsonify(analysis.model_dump())
