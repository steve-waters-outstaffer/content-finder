"""Main Flask application"""
import logging
import os
import time

from dotenv import load_dotenv
from flask import Flask, jsonify, request, g
from flask_cors import CORS
from werkzeug.exceptions import HTTPException

from api.search import search_bp
from api.scrape import scrape_bp
from api.analyze import analyze_bp
from api.synthesize import synthesize_bp
from api.intelligence import intelligence_bp
from api.intelligence_stages import stages_bp
from core.logging_config import configure_logging

# Load environment variables
load_dotenv()

configure_logging()
logger = logging.getLogger(__name__)


def create_app():
    """Create and configure Flask application"""
    logger.info("Initializing Flask application", extra={"operation": "app_init"})
    app = Flask(__name__)
    app.config['JSON_SORT_KEYS'] = False
    
    # Enable CORS for React frontend
    # CORS(app, origins=["http://localhost:5173", "http://127.0.0.1:5173", "https://content-finder-4bf70.web.app"])
    CORS(app, resources={r"/api/*": {"origins": ["http://localhost:5173", "http://127.0.0.1:5173", "https://content-finder-4bf70.web.app"]}}, supports_credentials=True)
    
    # Request timing and tracing
    @app.before_request
    def _req_start():
        g._start = time.time()
        # Pull Cloud Run trace header for GCP log correlation
        trace_header = request.headers.get("X-Cloud-Trace-Context", "")
        g._trace = trace_header.split("/", 1)[0] if trace_header else None

        logging.getLogger("request").info(
            "request_start",
            extra={
                "operation": "request_start",
                "method": request.method,
                "path": request.path,
                "content_length": request.content_length or 0,
                "remote_addr": request.headers.get("X-Forwarded-For", request.remote_addr),
                "user_agent": request.headers.get("User-Agent"),
                "trace": g._trace,
            },
        )

    @app.after_request
    def _req_end(response):
        duration_ms = int((time.time() - getattr(g, "_start", time.time())) * 1000)
        logging.getLogger("request").info(
            "request_end",
            extra={
                "operation": "request_end",
                "method": request.method,
                "path": request.path,
                "status": response.status_code,
                "duration_ms": duration_ms,
                "response_length": response.calculate_content_length() or 0,
                "trace": getattr(g, "_trace", None),
            },
        )
        return response

    @app.errorhandler(Exception)
    def _unhandled(error):
        # Log ALL exceptions with traceback
        error_logger = logging.getLogger("error")
        status = 500
        if isinstance(error, HTTPException):
            status = error.code or 500

        error_logger.exception(
            "unhandled_exception",
            extra={
                "operation": "unhandled_exception",
                "method": request.method,
                "path": request.path,
                "status": status,
                "content_length": request.content_length or 0,
                "trace": getattr(g, "_trace", None),
            },
        )
        msg = "Internal server error" if status >= 500 else (getattr(error, "description", "Bad request"))
        return jsonify({"error": msg}), status
    
    # Register blueprints
    app.register_blueprint(search_bp, url_prefix='/api')
    app.register_blueprint(scrape_bp, url_prefix='/api')
    app.register_blueprint(analyze_bp, url_prefix='/api')
    app.register_blueprint(synthesize_bp, url_prefix='/api')
    app.register_blueprint(intelligence_bp, url_prefix='/api')
    app.register_blueprint(stages_bp, url_prefix='/api')  # Staged VOC discovery
    
    @app.route('/')
    def health_check():
        """Health check endpoint"""
        logger.debug("Health check requested", extra={"operation": "health_check"})
        return jsonify({
            'status': 'healthy',
            'service': 'content-finder-backend',
            'endpoints': [
                '/api/search',
                '/api/scrape', 
                '/api/analyze',
                '/api/pipeline'
            ]
        })
    
    @app.route('/api/_diagnostics')
    def diagnostics():
        """Diagnostics endpoint for checking env config"""
        return jsonify({
            "ok": True,
            "gemini_key_present": bool(os.environ.get("GEMINI_API_KEY")),
            "firecrawl_key_present": bool(os.environ.get("FIRECRAWL_API_KEY")),
        })
    
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Endpoint not found'}), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({'error': 'Internal server error'}), 500
    
    return app


if __name__ == '__main__':
    app = create_app()
    logger.info(
        "Starting Flask server",
        extra={
            "operation": "app_start",
            "host": "0.0.0.0",
            "port": 5000,
        },
    )
    app.run(debug=True, host='0.0.0.0', port=5000)
