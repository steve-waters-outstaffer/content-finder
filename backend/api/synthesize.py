"""Content synthesis API endpoint."""
from flask import Blueprint, jsonify, request

from core.pipeline import ContentPipeline


synthesize_bp = Blueprint("synthesize", __name__)


@synthesize_bp.route("/synthesize", methods=["POST"])
def synthesize_content():
    """Synthesize insights from multiple content sources."""

    data = request.get_json() or {}
    query = data.get("query")
    contents = data.get("contents")  # Expect a list of {url, title, markdown}

    if not contents or not isinstance(contents, list):
        return jsonify({"error": "A list of content is required"}), 400

    if not query:
        return jsonify({"error": "A query or topic is required"}), 400

    try:
        pipeline = ContentPipeline()
        result = pipeline.synthesize_article(query, contents)
        return jsonify(result)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 500
