"""Main Flask application"""
import os
from dotenv import load_dotenv
from flask import Flask, jsonify
from flask_cors import CORS
from api.search import search_bp
from api.scrape import scrape_bp
from api.analyze import analyze_bp
from api.synthesize import synthesize_bp
from api.intelligence import intelligence_bp

# Load environment variables
load_dotenv()


def create_app():
    """Create and configure Flask application"""
    app = Flask(__name__)
    app.config['JSON_SORT_KEYS'] = False
    
    # Enable CORS for React frontend
    CORS(app, origins=["http://localhost:5173", "http://127.0.0.1:5173", "https://content-finder-4bf70.web.app"])
    
    # Register blueprints
    app.register_blueprint(search_bp, url_prefix='/api')
    app.register_blueprint(scrape_bp, url_prefix='/api')
    app.register_blueprint(analyze_bp, url_prefix='/api')
    app.register_blueprint(synthesize_bp, url_prefix='/api')
    app.register_blueprint(intelligence_bp, url_prefix='/api')
    
    @app.route('/')
    def health_check():
        """Health check endpoint"""
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
    
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Endpoint not found'}), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({'error': 'Internal server error'}), 500
    
    return app


if __name__ == '__main__':
    app = create_app()
    print("Starting Flask server on http://localhost:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)
