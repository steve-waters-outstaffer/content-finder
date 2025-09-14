"""Scraping API endpoint"""
from flask import Blueprint, request, jsonify
from core.pipeline import ContentPipeline


scrape_bp = Blueprint('scrape', __name__)


@scrape_bp.route('/scrape', methods=['POST'])
def scrape_urls():
    """Scrape multiple URLs"""
    data = request.get_json()
    urls = data.get('urls', [])
    formats = data.get('formats', ['markdown', 'html'])
    
    if not urls:
        return jsonify({'error': 'URLs are required'}), 400
    
    if not isinstance(urls, list):
        return jsonify({'error': 'URLs must be a list'}), 400
    
    try:
        pipeline = ContentPipeline()
        results = pipeline.scrape_urls(urls)
        return jsonify({
            'urls_requested': len(urls),
            'results': results,
            'successful': len([r for r in results if r.get('success', False)]),
            'failed': len([r for r in results if not r.get('success', True)])
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
