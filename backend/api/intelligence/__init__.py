"""Blueprint aggregation for intelligence-related endpoints."""
from __future__ import annotations

from flask import Blueprint

from .config import config_bp
from .sessions import sessions_bp
from .voc import voc_bp

intelligence_bp = Blueprint("intelligence", __name__)

# Register individual blueprints under the intelligence namespace
intelligence_bp.register_blueprint(config_bp)
intelligence_bp.register_blueprint(sessions_bp)
intelligence_bp.register_blueprint(voc_bp)

__all__ = ["intelligence_bp"]
