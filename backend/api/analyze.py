"""Analysis API endpoint"""
import logging
from flask import Blueprint, request, jsonify
from core.pipeline import ContentPipeline


analyze_bp = Blueprint('analyze', __name__)
logger = logging.getLogger(__name__)


@analyze_bp.route('/analyze', methods=['POST'])
def analyze_content():
    """Analyze content with Gemini AI"""
    data = request.get_json(silent=True) or {}
    content = data.get('content')
    custom_prompt = data.get('prompt')

    logger.info(
        "analyze_request",
        extra={
            "operation": "analyze_request",
            "content_length": len(content) if isinstance(content, str) else 0,
            "has_prompt": bool(custom_prompt),
        },
    )

    if not isinstance(content, str) or not content.strip():
        logger.warning("invalid_payload", extra={"operation": "analyze_request_invalid"})
        return jsonify({'error': 'Content is required'}), 400
    
    try:
        pipeline = ContentPipeline()
        result = pipeline.analyze_content(content, custom_prompt)
        logger.info("analyze_success", extra={"operation": "analyze_success"})
        return jsonify(result)
    except Exception as e:
        # Full traceback to logs, short message to client
        logger.exception("analyze_failed", extra={"operation": "analyze_failed"})
        return jsonify({'error': 'Analysis failed'}), 500
